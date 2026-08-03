"""Pure minimal-set planning for CTX.PATCH.1 candidate evaluations.

The planner selects a bounded, coherent proposal from already-evaluated files.
It has no filesystem, patching, validation-execution, or authority side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from pathlib import PurePosixPath
from typing import Any, Iterable, Iterator, Mapping


MAX_PROPOSED_SOURCE_FILES = 4
MAX_PROPOSED_VALIDATION_FILES = 4
MAX_PROPOSED_TOTAL_FILES = 8
MAX_SUPPLIED_CANDIDATES = 256

PATCH_SET_STATUSES = (
    "ready",
    "ready_with_review",
    "insufficient_evidence",
    "reread_required",
    "human_file_selection_required",
    "blocked",
)

PROPOSABLE_STATES = frozenset(
    {
        "eligible",
        "eligible_with_review",
        "validation_gap",
        "high_blast_radius_review",
    }
)

BLOCKED_STATES = frozenset(
    {
        "reread_required",
        "generated_source_redirect",
        "sensitive_blocked",
        "outside_scope",
        "forbidden",
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


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "as_dict"):
        rendered = value.as_dict()
        if not isinstance(rendered, Mapping):
            raise TypeError("candidate as_dict() must return a mapping")
        return dict(rendered)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("patch-set candidates must be records or mappings")


def _value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        if key in value:
            return value[key]
        nested = value.get("patchability")
        if isinstance(nested, Mapping) and key in nested:
            return nested[key]
        return default
    if hasattr(value, key):
        return getattr(value, key)
    nested = getattr(value, "patchability", None)
    return getattr(nested, key, default)


def _path(value: Any) -> str:
    return str(_value(value, "path", ""))


def _score(value: Any) -> int:
    raw = _value(value, "patchability_score", 0)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise TypeError("candidate patchability_score must be an integer")
    return max(0, min(100, raw))


def _state(value: Any) -> str:
    return str(_value(value, "candidate_state", "insufficient_evidence"))


def _looks_like_validation_path(path: str) -> bool:
    pure = PurePosixPath(path)
    parts = {part.casefold() for part in pure.parts}
    name = pure.name.casefold()
    return bool(
        parts & {"test", "tests", "spec", "specs"}
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    )


def _is_validation(value: Any) -> bool:
    role = str(_value(value, "role", "")).casefold()
    patch_role = str(_value(value, "patch_role", "")).casefold()
    return (
        role in {"validation", "test", "tests"}
        or patch_role in {"validation", "test"}
        or _looks_like_validation_path(_path(value))
    )


def _required_paths(value: Any) -> tuple[str, ...]:
    raw = _value(value, "required_paths", ())
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)):
        raise TypeError("required_paths must be an iterable of paths")
    return tuple(sorted({str(item) for item in raw if str(item)}))


def _validation_targets(value: Any) -> frozenset[str]:
    raw = _value(value, "validation_candidates", ())
    if raw is None or isinstance(raw, (str, bytes)):
        raw = (raw,) if raw else ()
    targets: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            targets.add(item)
        elif isinstance(item, Mapping):
            target = item.get("path", item.get("target"))
            if target:
                targets.add(str(target))
        elif hasattr(item, "target"):
            target = getattr(item, "target")
            if target:
                targets.add(str(target))
    return frozenset(targets)


def _strategy(value: Any) -> str:
    return str(_value(value, "strategy_id", "default") or "default")


def _coverage_rank(value: Any) -> int:
    raw = _value(value, "task_coverage", "unknown")
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, int):
        return max(0, min(100, raw))
    return {
        "complete": 100,
        "high": 90,
        "sufficient": 75,
        "partial": 40,
        "unknown": 0,
    }.get(str(raw).casefold(), 0)


def _candidate_sort_key(value: Any) -> tuple[int, int, str]:
    patch_role = str(_value(value, "patch_role", "")).casefold()
    role_rank = {
        "primary": 0,
        "primary_implementation_target": 0,
        "required_adjacent": 1,
        "adjacent_implementation": 1,
        "validation": 2,
        "test": 2,
        "optional": 4,
    }.get(patch_role, 3)
    return (role_rank, -_score(value), _path(value))


@dataclass(frozen=True, slots=True)
class PatchSetLimits(_RecordMapping):
    max_source_files: int = MAX_PROPOSED_SOURCE_FILES
    max_validation_files: int = MAX_PROPOSED_VALIDATION_FILES
    max_total_files: int = MAX_PROPOSED_TOTAL_FILES

    def __post_init__(self) -> None:
        for name in (
            "max_source_files",
            "max_validation_files",
            "max_total_files",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_source_files > MAX_PROPOSED_SOURCE_FILES:
            raise ValueError("source-file limit exceeds the CTX.PATCH.1 maximum")
        if self.max_validation_files > MAX_PROPOSED_VALIDATION_FILES:
            raise ValueError("validation-file limit exceeds the CTX.PATCH.1 maximum")
        if self.max_total_files > MAX_PROPOSED_TOTAL_FILES:
            raise ValueError("total-file limit exceeds the CTX.PATCH.1 maximum")

    def as_dict(self) -> dict[str, int]:
        return {
            "max_source_files": self.max_source_files,
            "max_validation_files": self.max_validation_files,
            "max_total_files": self.max_total_files,
        }


@dataclass(frozen=True, slots=True)
class ProposedPatchSet(_RecordMapping):
    status: str
    implementation_candidates: tuple[Any, ...]
    validation_candidates: tuple[Any, ...]
    supporting_context: tuple[Any, ...]
    blocked_candidates: tuple[Any, ...]
    limits: PatchSetLimits
    warnings: tuple[str, ...] = ()
    selected_strategy_id: str | None = None
    write_authority: bool = False
    patch_application_authority: bool = False
    human_approval_required: bool = True

    def __post_init__(self) -> None:
        if self.status not in PATCH_SET_STATUSES:
            raise ValueError(f"unknown proposed patch-set status: {self.status}")
        if self.write_authority is not False:
            raise ValueError("proposed patch sets never grant write authority")
        if self.patch_application_authority is not False:
            raise ValueError("proposed patch sets never grant patch authority")
        if self.human_approval_required is not True:
            raise ValueError("human approval must remain required")
        if len(self.implementation_candidates) > self.limits.max_source_files:
            raise ValueError("proposed source-file limit was exceeded")
        if len(self.validation_candidates) > self.limits.max_validation_files:
            raise ValueError("proposed validation-file limit was exceeded")
        if (
            len(self.implementation_candidates) + len(self.validation_candidates)
            > self.limits.max_total_files
        ):
            raise ValueError("proposed total-file limit was exceeded")
        paths = [
            _path(item)
            for group in (
                self.implementation_candidates,
                self.validation_candidates,
                self.supporting_context,
                self.blocked_candidates,
            )
            for item in group
        ]
        if len(paths) != len({path.casefold() for path in paths}):
            raise ValueError("a file may occupy only one patch-set classification")
        if tuple(sorted(set(self.warnings))) != self.warnings:
            raise ValueError("patch-set warnings must be deterministic")

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(
            _path(item)
            for item in self.implementation_candidates + self.validation_candidates
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "patch_candidate_status": self.status,
            "implementation_candidates": [
                _as_dict(item) for item in self.implementation_candidates
            ],
            "validation_candidates": [
                _as_dict(item) for item in self.validation_candidates
            ],
            "supporting_context": [
                _as_dict(item) for item in self.supporting_context
            ],
            "blocked_candidates": [
                _as_dict(item) for item in self.blocked_candidates
            ],
            "limits": self.limits.as_dict(),
            "selected_strategy_id": self.selected_strategy_id,
            "warnings": list(self.warnings),
            "write_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
            "patch_safety_bypassed": False,
        }


def _limits(
    max_source_files: int,
    max_validation_files: int,
    max_total_files: int,
) -> PatchSetLimits:
    # Oversized caller requests cannot relax the phase's hard maxima.
    return PatchSetLimits(
        max_source_files=min(max_source_files, MAX_PROPOSED_SOURCE_FILES),
        max_validation_files=min(
            max_validation_files, MAX_PROPOSED_VALIDATION_FILES
        ),
        max_total_files=min(max_total_files, MAX_PROPOSED_TOTAL_FILES),
    )


def build_proposed_patch_set(
    candidates: Iterable[Any],
    *,
    max_source_files: int = MAX_PROPOSED_SOURCE_FILES,
    max_validation_files: int = MAX_PROPOSED_VALIDATION_FILES,
    max_total_files: int = MAX_PROPOSED_TOTAL_FILES,
) -> ProposedPatchSet:
    """Choose the smallest supplied coherent candidate set within hard limits."""

    if isinstance(candidates, (str, bytes, Mapping)):
        raise TypeError("candidates must be an iterable of candidate records")
    selected_limits = _limits(
        max_source_files, max_validation_files, max_total_files
    )
    materialized = tuple(islice(iter(candidates), MAX_SUPPLIED_CANDIDATES + 1))
    if len(materialized) > MAX_SUPPLIED_CANDIDATES:
        raise ValueError(
            f"candidates exceed the defensive limit of {MAX_SUPPLIED_CANDIDATES}"
        )
    paths = tuple(_path(item) for item in materialized)
    if any(not path for path in paths):
        raise ValueError("every patch-set candidate requires a nonblank path")
    if len(paths) != len({path.casefold() for path in paths}):
        raise ValueError("patch-set candidates contain duplicate paths")
    for item in materialized:
        if _value(item, "write_authority", False) is not False:
            raise ValueError("candidate input attempts to grant write authority")
        if _value(item, "patch_application_authority", False) is not False:
            raise ValueError("candidate input attempts to grant patch authority")
        if _value(item, "human_approval_required", True) is not True:
            raise ValueError("candidate input attempts to bypass human approval")

    ordered = tuple(sorted(materialized, key=_candidate_sort_key))
    blocked = [item for item in ordered if _state(item) in BLOCKED_STATES]
    supporting = [
        item
        for item in ordered
        if _state(item) not in BLOCKED_STATES
        and not (
            _state(item) in PROPOSABLE_STATES and _score(item) >= 65
        )
    ]
    viable = [
        item
        for item in ordered
        if _state(item) in PROPOSABLE_STATES and _score(item) >= 65
    ]
    viable_sources = [item for item in viable if not _is_validation(item)]
    viable_validations = [item for item in viable if _is_validation(item)]
    warnings: set[str] = set()

    if not viable_sources:
        supporting.extend(viable_validations)
        blocked_states = {_state(item) for item in blocked}
        freshness_values = {
            str(_value(item, "receipt_freshness", "")) for item in blocked
        }
        if "reread_required" in blocked_states or freshness_values & {
            "changed",
            "unverifiable",
        }:
            status = "reread_required"
        elif blocked and not supporting:
            status = "blocked"
        else:
            status = "insufficient_evidence"
        return ProposedPatchSet(
            status=status,
            implementation_candidates=(),
            validation_candidates=(),
            supporting_context=tuple(sorted(supporting, key=_candidate_sort_key)),
            blocked_candidates=tuple(sorted(blocked, key=_candidate_sort_key)),
            limits=selected_limits,
            warnings=tuple(sorted(warnings)),
        )

    strategies: dict[str, list[Any]] = {}
    for item in viable_sources:
        strategies.setdefault(_strategy(item), []).append(item)
    strategy_quality: dict[str, tuple[int, int, int]] = {}
    for strategy_id, items in strategies.items():
        strategy_quality[strategy_id] = (
            max(_coverage_rank(item) for item in items),
            max(_score(item) for item in items),
            -len(items),
        )
    best_quality = max(strategy_quality.values())
    best_strategies = tuple(
        sorted(
            strategy_id
            for strategy_id, quality in strategy_quality.items()
            if quality == best_quality
        )
    )
    if len(best_strategies) != 1:
        warnings.add(
            "equally plausible unrelated patch strategies require human selection"
        )
        supporting.extend(viable)
        return ProposedPatchSet(
            status="human_file_selection_required",
            implementation_candidates=(),
            validation_candidates=(),
            supporting_context=tuple(sorted(supporting, key=_candidate_sort_key)),
            blocked_candidates=tuple(sorted(blocked, key=_candidate_sort_key)),
            limits=selected_limits,
            warnings=tuple(sorted(warnings)),
        )

    strategy_id = best_strategies[0]
    strategy_sources = tuple(
        sorted(strategies[strategy_id], key=_candidate_sort_key)
    )
    by_path = {_path(item): item for item in viable}
    explicit_primary = [
        item
        for item in strategy_sources
        if str(_value(item, "patch_role", "")).casefold()
        in {"primary", "primary_implementation_target"}
    ]
    selected_sources: dict[str, Any] = {}
    if explicit_primary:
        for item in explicit_primary:
            selected_sources[_path(item)] = item
    else:
        primary = min(strategy_sources, key=_candidate_sort_key)
        selected_sources[_path(primary)] = primary
    for item in strategy_sources:
        if bool(_value(item, "required_for_coherence", False)) or str(
            _value(item, "patch_role", "")
        ).casefold() in {"required_adjacent", "adjacent_implementation"}:
            selected_sources[_path(item)] = item

    unresolved: set[str] = set()
    pending = list(selected_sources.values())
    while pending:
        owner = pending.pop()
        for required_path in _required_paths(owner):
            required = by_path.get(required_path)
            if (
                required is None
                or _is_validation(required)
                or _strategy(required) != strategy_id
            ):
                unresolved.add(required_path)
                continue
            if required_path not in selected_sources:
                selected_sources[required_path] = required
                pending.append(required)

    if unresolved:
        warnings.add(
            "required coherent files lack eligible direct-read evidence: "
            + ", ".join(sorted(unresolved))
        )
        supporting.extend(viable)
        return ProposedPatchSet(
            status="insufficient_evidence",
            implementation_candidates=(),
            validation_candidates=(),
            supporting_context=tuple(sorted(supporting, key=_candidate_sort_key)),
            blocked_candidates=tuple(sorted(blocked, key=_candidate_sort_key)),
            limits=selected_limits,
            warnings=tuple(sorted(warnings)),
            selected_strategy_id=strategy_id,
        )

    ordered_sources = tuple(
        sorted(selected_sources.values(), key=_candidate_sort_key)
    )
    if len(ordered_sources) > min(
        selected_limits.max_source_files,
        selected_limits.max_total_files,
    ):
        warnings.add("required coherent source files exceed the bounded limits")
        supporting.extend(viable)
        return ProposedPatchSet(
            status="human_file_selection_required",
            implementation_candidates=(),
            validation_candidates=(),
            supporting_context=tuple(sorted(supporting, key=_candidate_sort_key)),
            blocked_candidates=tuple(sorted(blocked, key=_candidate_sort_key)),
            limits=selected_limits,
            warnings=tuple(sorted(warnings)),
            selected_strategy_id=strategy_id,
        )

    referenced_validation_paths = frozenset(
        target
        for item in ordered_sources
        for target in _validation_targets(item)
    )
    selected_validations = tuple(
        sorted(
            (
                item
                for item in viable_validations
                if _strategy(item) in {strategy_id, "default"}
                and (
                    _path(item) in referenced_validation_paths
                    or bool(_value(item, "required_for_coherence", False))
                    or str(_value(item, "patch_role", "")).casefold()
                    in {"validation", "test"}
                )
            ),
            key=_candidate_sort_key,
        )
    )
    validation_limit = min(
        selected_limits.max_validation_files,
        selected_limits.max_total_files - len(ordered_sources),
    )
    if len(selected_validations) > validation_limit:
        warnings.add(
            "required validation-file candidates exceed the bounded patch-set limits"
        )
        supporting.extend(viable)
        return ProposedPatchSet(
            status="human_file_selection_required",
            implementation_candidates=(),
            validation_candidates=(),
            supporting_context=tuple(sorted(supporting, key=_candidate_sort_key)),
            blocked_candidates=tuple(sorted(blocked, key=_candidate_sort_key)),
            limits=selected_limits,
            warnings=tuple(sorted(warnings)),
            selected_strategy_id=strategy_id,
        )

    selected_paths = {
        _path(item) for item in ordered_sources + selected_validations
    }
    supporting.extend(
        item for item in viable if _path(item) not in selected_paths
    )
    if len(viable_sources) > len(ordered_sources):
        warnings.add("non-required eligible files remained supporting context")
    if blocked:
        warnings.add("blocked candidate evidence remains outside the proposed set")

    review_required = bool(warnings) or bool(blocked) or any(
        _state(item) != "eligible"
        for item in ordered_sources + selected_validations
    )
    if selected_validations:
        review_required = True
        warnings.add("test modification remains subject to a separate policy")
    return ProposedPatchSet(
        status="ready_with_review" if review_required else "ready",
        implementation_candidates=ordered_sources,
        validation_candidates=selected_validations,
        supporting_context=tuple(sorted(supporting, key=_candidate_sort_key)),
        blocked_candidates=tuple(sorted(blocked, key=_candidate_sort_key)),
        limits=selected_limits,
        warnings=tuple(sorted(warnings)),
        selected_strategy_id=strategy_id,
    )


# Explicit spelling for callers that want to emphasize minimality.
plan_proposed_patch_set = build_proposed_patch_set
