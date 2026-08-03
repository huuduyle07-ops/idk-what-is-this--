"""Pure CTX.SELECT.1 composition, read-set planning, and contract rendering.

All inputs are already-supplied inventory metadata or lexical results.  This
module proposes bounded inspection and possible patch targets; it does not read
files, execute search, authorize writes, apply patches, or invoke repository
intelligence systems.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import islice
from pathlib import PurePosixPath
from typing import Any, Iterable, Iterator, Mapping, Sequence

from core.file_actionability import (
    EVIDENCE_WEIGHTS,
    MAX_SUPPLIED_ACTIONABILITY_EVIDENCE,
    MAX_SUPPLIED_RISK_ADJUSTMENTS,
    RISK_WEIGHTS,
    SCORE_BANDS,
)
from core.file_candidate_selector import (
    DEFAULT_LEXICAL_EXCLUDE_PATHS,
    MAX_EXPANSION_ROUNDS,
    MAX_LEXICAL_FILES,
    MAX_LEXICAL_EXCLUDE_PATHS,
    MAX_LEXICAL_INCLUDE_PATHS,
    MAX_LEXICAL_MATCHES,
    MAX_LEXICAL_MATCH_LENGTH,
    MAX_LEXICAL_TERMS,
    MAX_SUPPLIED_DISCOVERY_VALUES,
    MAX_SUPPLIED_LEXICAL_TERMS,
    MAX_SUPPLIED_SEARCH_PATHS,
    MEDIUM_REPOSITORY_MAX_READABLE_FILES,
    SMALL_REPOSITORY_MAX_READABLE_FILES,
    CandidateFilenameReport,
    LexicalSearchRequest,
    LexicalSearchResultSet,
    RankedCandidate,
    build_candidate_filename_report,
    build_lexical_search_request,
    consume_lexical_search_results,
    rank_candidates,
)
from core.file_capabilities import (
    EDITABILITY_STATES,
    INDEXABILITY_STATES,
    PARSER_SUPPORT_STATES,
    READABILITY_STATES,
    READ_POLICY_STATES,
    UNDERSTANDING_CONFIDENCE_STATES,
    FileCapability,
    classify_file_capability,
    normalize_repository_relative_path,
)


PHASE_ID = "CTX.SELECT.1"
CONTRACT_SCHEMA_VERSION = "ctx_select_1_v1"
CONTRACT_JSON_NAME = "candidate_selection_contract.json"
CONTRACT_MARKDOWN_NAME = "candidate_selection_contract.md"

MAX_PROPOSED_READS = 8
MAX_TOTAL_PROPOSED_READ_BYTES = 1_048_576
DEFAULT_PATCH_SCORE_THRESHOLD = 60
MAX_CANDIDATE_WARNINGS = 64

CANDIDATE_ACTIONS = (
    "propose_read",
    "propose_inspect_then_patch",
    "propose_patch_candidate",
    "supporting_context_only",
    "redirect_to_authoritative_source",
    "requires_human_approval",
    "exclude",
)

ESCALATION_OUTCOMES = (
    "direct_context_sufficient",
    "activation_graph_recommended",
    "canonical_intelligence_recommended",
    "human_file_selection_required",
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
class ProposedReadFile(_RecordMapping):
    path: str
    actionability_score: int
    estimated_bytes: int
    role: str
    selection_reason: str

    def __post_init__(self) -> None:
        if not 0 <= self.actionability_score <= 100:
            raise ValueError("proposed-read score must be bounded from 0 through 100")
        if self.estimated_bytes < 0:
            raise ValueError("proposed-read estimated bytes must be non-negative")

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "actionability_score": self.actionability_score,
            "estimated_bytes": self.estimated_bytes,
            "role": self.role,
            "selection_reason": self.selection_reason,
            "read_authority": False,
            "write_authority": False,
        }


@dataclass(frozen=True, slots=True)
class ExcludedReadFile(_RecordMapping):
    path: str
    reason: str
    recommended_strategy: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"path": self.path, "reason": self.reason}
        if self.recommended_strategy:
            result["recommended_strategy"] = self.recommended_strategy
        return result


@dataclass(frozen=True, slots=True)
class ProposedReadSet(_RecordMapping):
    selected: tuple[ProposedReadFile, ...]
    excluded: tuple[ExcludedReadFile, ...]
    total_estimated_bytes: int
    max_files: int
    max_total_bytes: int
    truncated: bool
    selection_reasons: tuple[tuple[str, str], ...]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.selected)

    def as_dict(self) -> dict[str, Any]:
        return {
            "selected": [item.as_dict() for item in self.selected],
            "excluded": [item.as_dict() for item in self.excluded],
            "total_estimated_bytes": self.total_estimated_bytes,
            "max_files": self.max_files,
            "max_total_bytes": self.max_total_bytes,
            "truncated": self.truncated,
            "selection_reasons": dict(self.selection_reasons),
            "read_authority": False,
            "write_authority": False,
        }


@dataclass(frozen=True, slots=True)
class ProposedPatchFile(_RecordMapping):
    path: str
    actionability_score: int
    recommended_action: str
    write_authority: bool
    validation_candidates: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.write_authority is not False:
            raise ValueError("proposed patch files can never carry write authority")
        if not 0 <= self.actionability_score <= 100:
            raise ValueError("proposed-patch score must be bounded from 0 through 100")

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "actionability_score": self.actionability_score,
            "recommended_action": self.recommended_action,
            "write_authority": False,
            "validation_candidates": list(self.validation_candidates),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ExcludedPatchFile(_RecordMapping):
    path: str
    reason: str
    redirect_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"path": self.path, "reason": self.reason}
        if self.redirect_path:
            result["redirect_path"] = self.redirect_path
        return result


@dataclass(frozen=True, slots=True)
class ProposedPatchSet(_RecordMapping):
    selected: tuple[ProposedPatchFile, ...]
    excluded: tuple[ExcludedPatchFile, ...]
    score_threshold: int
    write_authority: bool = False

    def __post_init__(self) -> None:
        if self.write_authority is not False:
            raise ValueError("proposed patch sets can never carry write authority")

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.selected)

    def as_dict(self) -> dict[str, Any]:
        return {
            "selected": [item.as_dict() for item in self.selected],
            "excluded": [item.as_dict() for item in self.excluded],
            "score_threshold": self.score_threshold,
            "write_authority": False,
        }


@dataclass(frozen=True, slots=True)
class ContextSelectionPlan(_RecordMapping):
    filename_report: CandidateFilenameReport
    lexical_search_request: LexicalSearchRequest
    lexical_search_results: LexicalSearchResultSet
    candidate_files: tuple[RankedCandidate, ...]
    proposed_read_files: ProposedReadSet
    proposed_patch_files: ProposedPatchSet
    escalation: str
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": PHASE_ID,
            "filename_report": self.filename_report.as_dict(),
            "lexical_search_request": self.lexical_search_request.as_dict(),
            "lexical_search_results": self.lexical_search_results.as_dict(),
            "candidate_files": [item.as_dict() for item in self.candidate_files],
            "proposed_read_files": self.proposed_read_files.as_dict(),
            "proposed_patch_files": self.proposed_patch_files.as_dict(),
            "escalation": self.escalation,
            "warnings": list(self.warnings),
            "write_authority": False,
        }


def _candidate_value(candidate: RankedCandidate | Mapping[str, Any], key: str) -> Any:
    if isinstance(candidate, Mapping):
        capability = candidate.get("capability")
        capability_keys = {
            "path",
            "size_bytes",
            "readability",
            "parser_support",
            "indexability",
            "direct_read_allowed",
            "read_policy",
            "editability",
            "understanding_confidence",
            "repository_contained",
            "symlink_escape",
            "generated",
            "vendor",
            "authoritative_source",
        }
        raw_capability: Mapping[str, Any] | None = None
        if isinstance(capability, Mapping):
            raw_capability = capability
        elif "path" in candidate:
            raw_capability = candidate
        if raw_capability is not None and key in capability_keys:
            safe_capability = classify_file_capability(
                {
                    **raw_capability,
                    "sensitive_policy": raw_capability.get(
                        "sensitive_policy", raw_capability.get("read_policy")
                    ),
                }
            )
            return getattr(safe_capability, key)
        if key in candidate:
            return candidate[key]
        decision = candidate.get("decision")
        if isinstance(decision, Mapping) and key in decision:
            return decision[key]
        return None
    if hasattr(candidate, key):
        return getattr(candidate, key)
    if hasattr(candidate.capability, key):
        return getattr(candidate.capability, key)
    if hasattr(candidate.decision, key):
        return getattr(candidate.decision, key)
    return None


def _candidate_path(candidate: RankedCandidate | Mapping[str, Any]) -> str:
    return str(_candidate_value(candidate, "path") or "")


def _candidate_score(candidate: RankedCandidate | Mapping[str, Any]) -> int:
    value = _candidate_value(candidate, "actionability_score")
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("candidate actionability score must be an integer")
    if not 0 <= value <= 100:
        raise ValueError("candidate actionability score must be bounded 0-100")
    return value


def _candidate_role(candidate: RankedCandidate | Mapping[str, Any]) -> str:
    return str(_candidate_value(candidate, "role") or "primary_or_supporting_target")


def _candidate_size(candidate: RankedCandidate | Mapping[str, Any]) -> int | None:
    value = _candidate_value(candidate, "size_bytes")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _candidate_action(candidate: RankedCandidate | Mapping[str, Any]) -> str:
    return str(_candidate_value(candidate, "action") or "")


def _candidate_evidence_kinds(
    candidate: RankedCandidate | Mapping[str, Any],
) -> frozenset[str]:
    if isinstance(candidate, RankedCandidate):
        return frozenset(item.kind for item in candidate.positive_evidence)
    raw = candidate.get("positive_evidence", ())
    return frozenset(
        str(item.get("kind"))
        for item in raw
        if isinstance(item, Mapping) and item.get("kind")
    )


def _candidate_validations(
    candidate: RankedCandidate | Mapping[str, Any],
    *,
    eligible_paths: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    value = _candidate_value(candidate, "validation_candidates") or ()
    if isinstance(value, (str, bytes)):
        raise TypeError("validation_candidates must be an iterable of paths")
    normalized_values: set[str] = set()
    for item in value:
        normalized = normalize_repository_relative_path(str(item))
        if normalized is None:
            continue
        if eligible_paths is not None:
            canonical = eligible_paths.get(normalized.casefold())
            if canonical is None:
                continue
            normalized = canonical
        normalized_values.add(normalized)
    return tuple(sorted(normalized_values))


def _looks_like_validation_path(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.casefold()
    return (
        any(
            part.casefold() in {"test", "tests", "spec", "specs", "__tests__"}
            for part in pure.parts[:-1]
        )
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith("_test.py")
    )


def _candidate_warnings(
    candidate: RankedCandidate | Mapping[str, Any],
) -> set[str]:
    value = _candidate_value(candidate, "warnings")
    if value is None:
        return set()
    if isinstance(value, str):
        return {value} if value else set()
    if isinstance(value, (bytes, Mapping)):
        raise TypeError("warnings must be a string or iterable of strings")
    materialized = tuple(islice(iter(value), MAX_CANDIDATE_WARNINGS + 1))
    if len(materialized) > MAX_CANDIDATE_WARNINGS:
        raise ValueError(
            "warnings exceeds the defensive input limit of "
            f"{MAX_CANDIDATE_WARNINGS}"
        )
    return {str(item) for item in materialized if str(item)}


def _candidate_sort_key(
    candidate: RankedCandidate | Mapping[str, Any],
) -> tuple[int, int, int, str]:
    kinds = _candidate_evidence_kinds(candidate)
    return (
        0 if "user_named_file" in kinds else 1,
        0 if "exact_filename_match" in kinds else 1,
        -_candidate_score(candidate),
        _candidate_path(candidate),
    )


def _selection_groups(
    ordered: Sequence[RankedCandidate | Mapping[str, Any]],
) -> tuple[tuple[str, tuple[RankedCandidate | Mapping[str, Any], ...]], ...]:
    if not ordered:
        return ()
    primary = ordered[0]
    primary_dir = PurePosixPath(_candidate_path(primary)).parent.as_posix()
    used = {_candidate_path(primary)}
    groups: list[tuple[str, tuple[RankedCandidate | Mapping[str, Any], ...]]] = [
        ("primary likely target", (primary,))
    ]
    for role, reason in (
        ("dependency_or_caller", "immediate dependency or caller"),
        ("validation", "corresponding validation or test"),
        ("configuration", "task-relevant configuration"),
    ):
        matches = tuple(
            item
            for item in ordered
            if _candidate_role(item) == role and _candidate_path(item) not in used
        )
        if matches:
            groups.append((reason, matches))
            used.add(_candidate_path(matches[0]))
    contrasting = tuple(
        item
        for item in ordered
        if _candidate_path(item) not in used
        and PurePosixPath(_candidate_path(item)).parent.as_posix() != primary_dir
    )
    if contrasting:
        groups.append(("contrasting candidate for ambiguity", contrasting))
        used.add(_candidate_path(contrasting[0]))
    remainder = tuple(item for item in ordered if _candidate_path(item) not in used)
    if remainder:
        groups.append(("next highest bounded evidence", remainder))
    return tuple(groups)


def build_proposed_read_set(
    candidates: Iterable[RankedCandidate | Mapping[str, Any]],
    *,
    max_files: int = MAX_PROPOSED_READS,
    max_total_bytes: int = MAX_TOTAL_PROPOSED_READ_BYTES,
    diversity_policy: bool = True,
) -> ProposedReadSet:
    """Choose a diverse, bounded inspection proposal; no read is performed."""

    file_limit = max(0, min(int(max_files), MAX_PROPOSED_READS))
    byte_limit = max(0, min(int(max_total_bytes), MAX_TOTAL_PROPOSED_READ_BYTES))
    materialized = tuple(candidates)
    paths = [_candidate_path(item).casefold() for item in materialized]
    if len(paths) != len(set(paths)):
        raise ValueError("read-set candidates contain duplicate canonical paths")
    ordered = tuple(sorted(materialized, key=_candidate_sort_key))
    groups = (
        _selection_groups(ordered)
        if diversity_policy
        else (("highest bounded evidence", ordered),)
    )

    selected: list[ProposedReadFile] = []
    excluded: dict[str, ExcludedReadFile] = {}
    total = 0
    considered: set[str] = set()

    def consider(
        item: RankedCandidate | Mapping[str, Any],
        reason: str,
    ) -> bool:
        nonlocal total
        path = _candidate_path(item)
        if path in considered:
            return False
        considered.add(path)
        action = _candidate_action(item)
        direct_allowed = bool(_candidate_value(item, "direct_read_allowed"))
        can_propose_read = _candidate_value(item, "can_propose_read")
        if action in {"exclude", "requires_human_approval"} or not direct_allowed:
            excluded[path] = ExcludedReadFile(path, "security_or_readability_gate")
            return False
        if can_propose_read is False:
            excluded[path] = ExcludedReadFile(path, "candidate_action_gate")
            return False
        size = _candidate_size(item)
        if size is None:
            excluded[path] = ExcludedReadFile(
                path,
                "unknown_size",
                "request a smaller bounded range in CTX.READ.1 after runtime revalidation",
            )
            return False
        if size < 0:
            excluded[path] = ExcludedReadFile(path, "invalid_size")
            return False
        if len(selected) >= file_limit:
            excluded[path] = ExcludedReadFile(path, "file_limit")
            return False
        if size > byte_limit - total:
            excluded[path] = ExcludedReadFile(
                path,
                "byte_limit",
                "request a smaller bounded range in CTX.READ.1",
            )
            return False
        selected.append(
            ProposedReadFile(
                path=path,
                actionability_score=_candidate_score(item),
                estimated_bytes=size,
                role=_candidate_role(item),
                selection_reason=reason,
            )
        )
        total += size
        return True

    for reason, group in groups:
        if len(selected) >= file_limit:
            break
        # Each diversity role gets its strongest viable candidate before fill.
        for item in group:
            if consider(item, reason):
                break

    for item in ordered:
        if _candidate_path(item) in considered:
            continue
        consider(item, "next highest bounded evidence")

    selected_paths = {item.path for item in selected}
    for item in ordered:
        path = _candidate_path(item)
        if path not in selected_paths and path not in excluded:
            excluded[path] = ExcludedReadFile(path, "not_selected_within_budget")

    selected_tuple = tuple(selected)
    excluded_tuple = tuple(excluded[path] for path in sorted(excluded))
    return ProposedReadSet(
        selected=selected_tuple,
        excluded=excluded_tuple,
        total_estimated_bytes=total,
        max_files=file_limit,
        max_total_bytes=byte_limit,
        truncated=bool(excluded_tuple),
        selection_reasons=tuple(
            (item.path, item.selection_reason) for item in selected_tuple
        ),
    )


def classify_proposed_patch_files(
    candidates: Iterable[RankedCandidate | Mapping[str, Any]],
    *,
    proposed_read_set: ProposedReadSet | None = None,
    score_threshold: int = DEFAULT_PATCH_SCORE_THRESHOLD,
) -> ProposedPatchSet:
    """Classify plausible patch targets while keeping write authority false."""

    materialized = tuple(candidates)
    read_set = proposed_read_set or build_proposed_read_set(materialized)
    readable_paths = set(read_set.paths)
    threshold = max(DEFAULT_PATCH_SCORE_THRESHOLD, min(100, int(score_threshold)))
    selected: list[ProposedPatchFile] = []
    excluded: list[ExcludedPatchFile] = []
    eligible_validation_paths: dict[str, str] = {}
    for item in materialized:
        validation_path = _candidate_path(item)
        if not (
            bool(_candidate_value(item, "direct_read_allowed"))
            and _candidate_value(item, "read_policy") == "auto_read_allowed"
            and _candidate_value(item, "readability")
            in {"readable_text", "readable_limited"}
            and _candidate_value(item, "editability")
            not in {
                "sensitive_requires_approval",
                "outside_scope",
                "opaque",
                "forbidden",
            }
            and (
                _candidate_role(item) == "validation"
                or _looks_like_validation_path(validation_path)
            )
        ):
            continue
        eligible_validation_paths[validation_path.casefold()] = validation_path

    for candidate in sorted(materialized, key=_candidate_sort_key):
        path = _candidate_path(candidate)
        score = _candidate_score(candidate)
        editability = str(_candidate_value(candidate, "editability") or "forbidden")
        readability = str(_candidate_value(candidate, "readability") or "unreadable")
        contained = bool(_candidate_value(candidate, "repository_contained"))
        generated = bool(_candidate_value(candidate, "generated"))
        vendor = bool(_candidate_value(candidate, "vendor"))
        action = _candidate_action(candidate)
        redirect = _candidate_value(candidate, "authoritative_source")
        kinds = _candidate_evidence_kinds(candidate)

        reason: str | None = None
        if path not in readable_paths:
            reason = "not_in_proposed_read_set"
        elif not contained:
            reason = "outside_repository"
        elif readability not in {"readable_text", "readable_limited"}:
            reason = "unacceptable_readability"
        elif generated or vendor:
            reason = "generated_or_vendor"
        elif editability not in {"editable", "editable_with_review"}:
            reason = "editability_gate"
        elif score < threshold:
            reason = "below_patch_score_threshold"
        elif not (
            kinds
            & {
                "user_named_file",
                "user_named_symbol",
                "test_pair",
                "direct_import_reference",
                "direct_symbol_reference",
                "lexical_match",
                "task_term_match",
                "recent_change_hint",
            }
        ):
            reason = "filename_only_evidence"
        elif action not in {"propose_patch_candidate", "propose_inspect_then_patch"}:
            reason = "candidate_action_gate"

        if reason:
            excluded.append(
                ExcludedPatchFile(
                    path,
                    reason,
                    str(redirect) if redirect else None,
                )
            )
            continue

        validations = _candidate_validations(
            candidate,
            eligible_paths=eligible_validation_paths,
        )
        warnings = _candidate_warnings(candidate)
        if not validations:
            warnings.add("validation_gap: no validation candidate supplied")
        if editability == "editable_with_review":
            warnings.add("editability review is required")
        selected.append(
            ProposedPatchFile(
                path=path,
                actionability_score=score,
                recommended_action="inspect_then_patch",
                write_authority=False,
                validation_candidates=validations,
                warnings=tuple(sorted(str(item) for item in warnings)),
            )
        )

    selected_paths = set(readable_paths)
    if not all(item.path in selected_paths for item in selected):
        raise AssertionError("proposed patch files must be a subset of proposed reads")
    return ProposedPatchSet(
        selected=tuple(selected),
        excluded=tuple(sorted(excluded, key=lambda item: item.path)),
        score_threshold=threshold,
        write_authority=False,
    )


build_proposed_patch_set = classify_proposed_patch_files


def build_context_selection_plan(
    capabilities: Iterable[FileCapability | Mapping[str, Any]],
    *,
    task_terms: Iterable[str] = (),
    user_named_files: Iterable[str] = (),
    user_named_symbols: Iterable[str] = (),
    supplied_lexical_results: Iterable[Mapping[str, Any]] = (),
    include_paths: Iterable[str] = (),
    reference_evidence: Mapping[str, Iterable[Mapping[str, Any] | str]] | None = None,
    risk_hints: Mapping[str, Iterable[Any]] | None = None,
    recent_change_hints: Iterable[str] = (),
    vector_database_available: bool | None = None,
    embedding_provider_enabled: bool | None = None,
    canonical_manifest_available: bool | None = None,
    canonical_identity_state: str = "uninitialized",
) -> ContextSelectionPlan:
    """Compose CTX.SELECT.1 using supplied data; external-state flags are advisory."""

    def bounded_values(
        values: Iterable[Any],
        *,
        limit: int,
        label: str,
    ) -> tuple[Any, ...]:
        if isinstance(values, (str, bytes)):
            raise TypeError(f"{label} must be an iterable of values")
        captured = tuple(islice(iter(values), limit + 1))
        if len(captured) > limit:
            raise ValueError(
                f"{label} exceeds the defensive input limit of {limit}"
            )
        return captured

    records = tuple(capabilities)
    per_term_source_limit = MAX_SUPPLIED_LEXICAL_TERMS // 2
    task_term_values = bounded_values(
        task_terms,
        limit=per_term_source_limit,
        label="task_terms",
    )
    named_file_values = bounded_values(
        user_named_files,
        limit=MAX_SUPPLIED_DISCOVERY_VALUES,
        label="user_named_files",
    )
    named_symbol_values = bounded_values(
        user_named_symbols,
        limit=per_term_source_limit,
        label="user_named_symbols",
    )
    recent_values = bounded_values(
        recent_change_hints,
        limit=MAX_SUPPLIED_DISCOVERY_VALUES,
        label="recent_change_hints",
    )
    filename_report = build_candidate_filename_report(
        records,
        task_terms=task_term_values,
        user_named_files=named_file_values,
        user_named_symbols=named_symbol_values,
        recent_change_hints=recent_values,
    )
    terms = task_term_values + named_symbol_values
    requested_include_paths = bounded_values(
        include_paths,
        limit=MAX_SUPPLIED_SEARCH_PATHS,
        label="include_paths",
    )
    safe_readable_paths = tuple(
        sorted(
            {
                _candidate_path(item)
                for item in records
                if bool(_candidate_value(item, "direct_read_allowed"))
                and _candidate_value(item, "read_policy") == "auto_read_allowed"
                and _candidate_value(item, "readability")
                in {"readable_text", "readable_limited"}
            }
        )
    )
    if requested_include_paths:
        normalized_prefixes = tuple(
            normalized
            for raw in requested_include_paths
            if (
                normalized := normalize_repository_relative_path(
                    str(raw).replace("\\", "/").rstrip("/")
                )
            )
            is not None
        )
        planned_include_paths = tuple(
            path
            for path in safe_readable_paths
            if any(
                path == prefix or path.startswith(prefix + "/")
                for prefix in normalized_prefixes
            )
        )
        if len(planned_include_paths) > MAX_SUPPLIED_SEARCH_PATHS:
            raise ValueError(
                "expanded safe include paths exceed the defensive input limit of "
                f"{MAX_SUPPLIED_SEARCH_PATHS}"
            )
    elif filename_report.repository_tier == "small":
        planned_include_paths = filename_report.complete_relative_paths
    else:
        planned_include_paths = tuple(
            path
            for path in filename_report.candidate_files
            if path in set(safe_readable_paths)
        )
    request = build_lexical_search_request(
        terms,
        include_paths=planned_include_paths,
        match_none=bool(requested_include_paths and not planned_include_paths),
    )
    lexical = consume_lexical_search_results(
        supplied_lexical_results,
        request=request,
        capabilities=records,
    )
    ranked = rank_candidates(
        records,
        filename_report=filename_report,
        lexical_results=lexical,
        reference_evidence=reference_evidence,
        risk_hints=risk_hints,
    )
    reads = build_proposed_read_set(ranked)
    patches = classify_proposed_patch_files(
        ranked,
        proposed_read_set=reads,
    )

    warnings: set[str] = set()
    if vector_database_available is False:
        warnings.add("vector database unavailable; lexical direct-context selection remains usable")
    if embedding_provider_enabled is False:
        warnings.add("embedding provider disabled; no embedding is required")
    if canonical_manifest_available is False:
        warnings.add("canonical manifest unavailable; supplied inventory remains sufficient")
    if canonical_identity_state not in {
        "uninitialized",
        "initial_confirmation_required",
        "major_change_confirmation_required",
        "blocked",
        "confirmed",
    }:
        warnings.add("unknown canonical identity state was treated as non-authoritative")

    if not reads.selected:
        escalation = "human_file_selection_required"
    elif filename_report.repository_tier == "large" and (
        not ranked or ranked[0].actionability_score < 60
    ):
        escalation = "canonical_intelligence_recommended"
    elif sum(item.role == "dependency_or_caller" for item in ranked) >= 4 and (
        not ranked or ranked[0].actionability_score < 80
    ):
        escalation = "activation_graph_recommended"
    else:
        escalation = "direct_context_sufficient"

    return ContextSelectionPlan(
        filename_report=filename_report,
        lexical_search_request=request,
        lexical_search_results=lexical,
        candidate_files=ranked,
        proposed_read_files=reads,
        proposed_patch_files=patches,
        escalation=escalation,
        warnings=tuple(sorted(warnings)),
    )


def build_candidate_selection_contract() -> dict[str, Any]:
    """Return the deterministic CTX.SELECT.1 contract artifact payload."""

    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "contract_status": "complete",
        "mission": (
            "Deterministically discover and rank repository files for proposed "
            "direct inspection without vector retrieval or canonical indexing."
        ),
        "authority_separation": {
            "invariant": "relevance_score != read_authority != write_authority",
            "read_authority_granted": False,
            "write_authority_granted": False,
            "approved_writable_files_produced": False,
        },
        "candidate_set_hierarchy": [
            "repository_files",
            "candidate_files",
            "proposed_read_files",
            "proposed_patch_files",
            "approved_writable_files",
        ],
        "produced_sets": [
            "candidate_files",
            "proposed_read_files",
            "proposed_patch_files",
        ],
        "capability_states": {
            "readability": list(READABILITY_STATES),
            "parser_support": list(PARSER_SUPPORT_STATES),
            "indexability": list(INDEXABILITY_STATES),
            "editability": list(EDITABILITY_STATES),
            "read_policy": list(READ_POLICY_STATES),
            "understanding_confidence": list(UNDERSTANDING_CONFIDENCE_STATES),
            "hard_rule": (
                "SUPPORTED_EXTENSIONS controls canonical parser/index eligibility, "
                "not whether safe text may be proposed for direct reading."
            ),
        },
        "repository_size_strategy": {
            "small": {
                "readable_file_count": f"0-{SMALL_REPOSITORY_MAX_READABLE_FILES}",
                "complete_safe_paths": True,
                "basic_capability_metadata": True,
                "bounded_lexical_scope": "all safe readable inventory members",
            },
            "medium": {
                "readable_file_count": (
                    f"{SMALL_REPOSITORY_MAX_READABLE_FILES + 1}-"
                    f"{MEDIUM_REPOSITORY_MAX_READABLE_FILES}"
                ),
                "complete_safe_paths": False,
                "outputs": [
                    "root entries",
                    "depth-limited directory synopsis",
                    "entrypoints",
                    "name matches",
                    "bounded lexical matches",
                    "top candidates",
                ],
            },
            "large": {
                "readable_file_count": f">{MEDIUM_REPOSITORY_MAX_READABLE_FILES}",
                "complete_safe_paths": False,
                "full_repository_context_dump": False,
                "bounded_directory_file_counts": True,
                "bounded_file_type_counts": True,
            },
            "thresholds_configurable_and_test_pinned": True,
        },
        "evidence_sources": {
            kind: {
                "weight": EVIDENCE_WEIGHTS[kind],
                "definition": kind.replace("_", " "),
            }
            for kind in sorted(EVIDENCE_WEIGHTS)
        },
        "scoring_stages": ["inventory", "filename_match", "lexical_search"],
        "lexical_search_limits": {
            "max_terms": MAX_LEXICAL_TERMS,
            "max_include_paths": MAX_LEXICAL_INCLUDE_PATHS,
            "max_exclude_paths": MAX_LEXICAL_EXCLUDE_PATHS,
            "max_matches": MAX_LEXICAL_MATCHES,
            "max_files": MAX_LEXICAL_FILES,
            "max_match_length": MAX_LEXICAL_MATCH_LENGTH,
            "max_expansion_rounds": MAX_EXPANSION_ROUNDS,
            "default_exclude_paths": list(DEFAULT_LEXICAL_EXCLUDE_PATHS),
            "match_kind": "literal",
            "case_sensitive_option": True,
            "case_insensitive_option": True,
            "whole_token_preference_metadata": True,
            "executes_search": False,
            "safe_inventory_filter_required": True,
            "production_execution_authorized": False,
            "sensitive_or_binary_excerpts_allowed": False,
        },
        "actionability_score": {
            "range": [0, 100],
            "integer_only": True,
            "positive_weights": dict(sorted(EVIDENCE_WEIGHTS.items())),
            "risk_weights": dict(sorted(RISK_WEIGHTS.items())),
            "bands": [
                {"minimum": low, "maximum": high, "label": label}
                for low, high, label in SCORE_BANDS
            ],
            "duplicate_evidence_counted_twice": False,
            "max_supplied_evidence": MAX_SUPPLIED_ACTIONABILITY_EVIDENCE,
            "max_supplied_risk_adjustments": MAX_SUPPLIED_RISK_ADJUSTMENTS,
            "permission_semantics": False,
        },
        "editability_state_overrides": {
            "editable": "may be considered after evidence and read gates",
            "editable_with_review": "may be considered with a warning",
            "read_only": "proposed read only",
            "generated_do_not_edit": "redirect to authoritative source",
            "sensitive_requires_approval": "no automatic read or patch",
            "outside_scope": "exclude",
            "opaque": "exclude from textual reads",
            "forbidden": "exclude regardless of score",
        },
        "read_set_budget": {
            "max_files": MAX_PROPOSED_READS,
            "max_total_bytes": MAX_TOTAL_PROPOSED_READ_BYTES,
            "unknown_size_behavior": "fail_closed_with_bounded_read_recommendation",
            "diversity_order": [
                "primary target",
                "dependency or caller",
                "validation or test",
                "configuration",
                "contrasting candidate",
            ],
        },
        "patch_candidate_rules": {
            "minimum_score": DEFAULT_PATCH_SCORE_THRESHOLD,
            "must_be_in_proposed_read_set": True,
            "filename_only_evidence_sufficient": False,
            "repository_containment_required": True,
            "generated_vendor_sensitive_forbidden": True,
            "validation_required_or_gap_warning": True,
            "validation_paths_inventory_and_policy_screened": True,
            "write_authority": False,
        },
        "sensitive_file_rules": {
            "source_code": "auto_read_allowed",
            ".env.example": "auto_read_allowed",
            ".env": "explicit_human_approval_required",
            "private_keys": "hard_no_auto_read",
            "credential_browser_session_stores": "hard_no_auto_read",
            "unmanaged_binary_files": "hard_no_auto_read",
            "outside_root_or_symlink_escape": "hard_no_auto_read",
            "high_relevance_overrides_forbidden_state": False,
        },
        "vector_index_identity_independence": {
            "vector_database_required": False,
            "embedding_provider_required": False,
            "embedding_signature_required": False,
            "canonical_manifest_required": False,
            "canonical_identity_confirmation_required": False,
            "identity_states_supported": [
                "uninitialized",
                "initial_confirmation_required",
                "major_change_confirmation_required",
                "blocked",
            ],
            "database_import_or_write": False,
            "manifest_operation": False,
            "activation_graph_construction": False,
        },
        "escalation_policy": list(ESCALATION_OUTCOMES),
        "phase_boundaries": {
            "production_file_reads": False,
            "patch_application": False,
            "write_authority": False,
            "canonical_indexing": False,
            "vector_or_embedding_calls": False,
            "database_operations": False,
            "activation_graph_execution": False,
            "model_or_api_calls": False,
            "subprocess_or_shell_search": False,
            "background_workers": False,
        },
        "deferred_runtime_work": [
            "bounded content reads with runtime containment and symlink revalidation",
            "reference expansion after direct inspection",
            "patch authorization and human approval",
            "optional Activation Graph or canonical intelligence escalation",
        ],
        "recommended_next_phase": "CTX.READ.1 - Bounded Direct File Read Runtime",
    }


def render_candidate_selection_contract_json(
    contract: Mapping[str, Any] | None = None,
) -> str:
    payload = build_candidate_selection_contract() if contract is None else dict(contract)
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_candidate_selection_contract_markdown(
    contract: Mapping[str, Any] | None = None,
) -> str:
    data = build_candidate_selection_contract() if contract is None else dict(contract)
    lexical = data["lexical_search_limits"]
    read_budget = data["read_set_budget"]
    lines = [
        "# CTX.SELECT.1 - Bounded Candidate Discovery & File Actionability Contract",
        "",
        "Status: complete (contract and pure selection only)",
        "",
        "## Authority Boundary",
        "",
        "`relevance score != read authority != write authority`. This phase grants no read authority and no write authority.",
        "",
        "## Candidate-Set Hierarchy",
        "",
        "`repository_files >= candidate_files >= proposed_read_files >= proposed_patch_files >= approved_writable_files`.",
        "CTX.SELECT.1 emits only the middle three proposal sets; it never emits approved writable files.",
        "",
        "## Capability Model",
        "",
        "Readability, parser support, indexability, direct-read policy, editability, and understanding confidence are independent states.",
        "`SUPPORTED_EXTENSIONS` controls canonical parser/index eligibility, not whether safe text can be useful as raw direct context.",
        "",
        "## Repository Tiers",
        "",
        f"- Small: 0-{SMALL_REPOSITORY_MAX_READABLE_FILES} readable files; expose the complete safe relative-path list and basic capability metadata.",
        f"- Medium: {SMALL_REPOSITORY_MAX_READABLE_FILES + 1}-{MEDIUM_REPOSITORY_MAX_READABLE_FILES}; expose bounded synopsis and candidates.",
        f"- Large: more than {MEDIUM_REPOSITORY_MAX_READABLE_FILES}; emit bounded directory/file-type counts and never a full repository context dump.",
        "",
        "## Candidate Discovery",
        "",
        "Inventory -> filename/path evidence -> supplied bounded lexical evidence -> direct-reference/test-pair evidence -> integer scoring.",
        "No vector similarity is required.",
        "",
        "## Bounded Lexical Search Contract",
        "",
        f"At most {lexical['max_terms']} terms, {lexical['max_include_paths']} include paths, {lexical['max_exclude_paths']} exclude paths, {lexical['max_matches']} matches across {lexical['max_files']} files, {lexical['max_match_length']} characters per excerpt, and {lexical['max_expansion_rounds']} expansion rounds.",
        "The phase only builds requests and consumes supplied results; it executes no grep, ripgrep, shell, or subprocess.",
        "Every future executor must apply the supplied safe-inventory filter; this contract grants no production execution authority.",
        "Sensitive and binary excerpts are never retained.",
        "",
        "## File Actionability Score",
        "",
        "Scores are deterministic integers from 0 to 100 with inspectable positive evidence, risk adjustments, and stage history.",
        "Duplicate evidence is not counted twice, and forbidden state overrides score-based action.",
        "",
        "## Editability Overrides",
        "",
        "Generated output redirects to its authoritative source; read-only files remain context only; sensitive files require approval; opaque, outside-scope, and forbidden files are excluded.",
        "",
        "## Proposed Read Set",
        "",
        f"At most {read_budget['max_files']} files and {read_budget['max_total_bytes']} total estimated bytes, with target/dependency/test/configuration diversity.",
        "Unknown sizes fail closed and may be reconsidered only through a smaller bounded runtime read strategy.",
        "",
        "## Proposed Patch Candidates",
        "",
        "A patch candidate must already be in the proposed read set, have non-filename grounding, acceptable editability/readability, repository containment, and validation evidence or an explicit validation-gap warning.",
        "Every proposed patch candidate carries `write_authority: false`.",
        "",
        "## Sensitive and Forbidden Files",
        "",
        "`.env.example` is safe placeholder context; `.env` requires explicit approval; private keys, credential/browser/session stores, unmanaged binaries, outside-root paths, symlink escapes, and repository-forbidden paths are hard exclusions.",
        "A high relevance score never overrides these gates.",
        "",
        "## Vector, Index, Identity, and Graph Independence",
        "",
        "Candidate discovery works without a vector database, embeddings, embedding signatures, canonical manifests, or confirmed canonical identity.",
        "It performs no index/manifest operation, DB write, graph construction, model/API call, or production file read.",
        "",
        "## Deferred Runtime Work",
        "",
        "Runtime content reads, reference expansion, patch authorization, human approval, and optional graph/index escalation are deferred.",
        "",
        "## Recommended Next Phase",
        "",
        "CTX.READ.1 - Bounded Direct File Read Runtime (recommended only; not started or authorized).",
        "",
    ]
    return "\n".join(lines)
