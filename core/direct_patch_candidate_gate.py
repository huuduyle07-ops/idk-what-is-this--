"""CTX.PATCH.1 pure Direct Context patch-candidate gate.

The gate consumes immutable inventory metadata, CTX.READ receipts, supplied
current file identities, and deterministic task evidence.  It proposes a
bounded set of modification candidates but cannot generate a diff, write a
file, run validation, bypass patch safety, or grant patch authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from pathlib import PurePosixPath
from typing import Any, Iterable, Iterator, Mapping

from core.direct_context_runtime import compute_repository_inventory_identity
from core.direct_read_receipt import (
    DirectReadReceipt,
    ReceiptFreshnessDecision,
    verify_direct_read_receipt,
)
from core.file_capabilities import (
    FileCapability,
    classify_file_capability,
)
from core.file_patchability import (
    PatchabilityEvidence,
    PatchabilityRiskAdjustment,
    PatchabilityScore,
    calculate_patchability_score,
)
from core.proposed_patch_set import (
    MAX_PROPOSED_SOURCE_FILES,
    MAX_PROPOSED_TOTAL_FILES,
    MAX_PROPOSED_VALIDATION_FILES,
    PatchSetLimits,
    ProposedPatchSet,
    build_proposed_patch_set,
)
from core.repository_inventory import RepositoryInventory
from core.repository_path_policy import is_safe_repository_relative_path


PHASE_ID = "CTX.PATCH.1"
MAX_SUPPLIED_CANDIDATES = 256
MAX_DIRECT_READ_RECEIPTS = 8
MAX_PATH_EVIDENCE = 128
MAX_TARGET_RANGES = 8
MAX_PRESERVATION_ITEMS = 16
MAX_VALIDATION_CANDIDATES = 16
MAX_REQUIRED_PATHS = 8
MAX_WARNINGS = 128
MAX_ERRORS = 32

CANDIDATE_STATES = (
    "eligible",
    "eligible_with_review",
    "insufficient_evidence",
    "reread_required",
    "validation_gap",
    "read_only_context",
    "generated_source_redirect",
    "sensitive_blocked",
    "high_blast_radius_review",
    "outside_scope",
    "forbidden",
)

BLAST_RADIUS_LEVELS = ("low", "medium", "high", "critical", "unknown")
VALIDATION_KINDS = frozenset(
    {
        "pytest",
        "unit_test",
        "integration_test",
        "compile",
        "linter",
        "type_check",
        "static_analysis",
        "known_validation_command",
        "manual",
    }
)

DIRECT_QUALIFYING_EVIDENCE = frozenset(
    {
        "direct_read_target_confirmation",
        "direct_symbol_reference_confirmation",
        "localized_defect_evidence",
        "authoritative_source_confidence",
    }
)

CONFIGURATION_SUFFIXES = frozenset(
    {".cfg", ".conf", ".ini", ".json", ".toml", ".yaml", ".yml"}
)
CONFIGURATION_NAMES = frozenset(
    {
        ".env.example",
        ".env.sample",
        ".env.template",
        "docker-compose.yml",
        "docker-compose.yaml",
        "pyproject.toml",
        "package.json",
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


@dataclass(frozen=True, slots=True, order=True)
class TargetRange(_RecordMapping):
    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.start_line, bool)
            or isinstance(self.end_line, bool)
            or not isinstance(self.start_line, int)
            or not isinstance(self.end_line, int)
            or self.start_line <= 0
            or self.end_line < self.start_line
        ):
            raise ValueError("target ranges must be positive and ordered")

    def as_dict(self) -> dict[str, int]:
        return {"start_line": self.start_line, "end_line": self.end_line}


@dataclass(frozen=True, slots=True)
class ChangeIntention(_RecordMapping):
    summary: str
    target_ranges: tuple[TargetRange, ...]
    expected_behavior_change: str
    must_preserve: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.summary.strip() or len(self.summary) > 1_000:
            raise ValueError("change-intention summary must be bounded and nonblank")
        if (
            not self.expected_behavior_change.strip()
            or len(self.expected_behavior_change) > 1_000
        ):
            raise ValueError(
                "expected behavior change must be bounded and nonblank"
            )
        if len(self.target_ranges) > MAX_TARGET_RANGES:
            raise ValueError("change intention exceeds the target-range limit")
        if self.target_ranges != tuple(sorted(set(self.target_ranges))):
            raise ValueError("target ranges must be unique and deterministic")
        if len(self.must_preserve) > MAX_PRESERVATION_ITEMS:
            raise ValueError("change intention exceeds the preservation-item limit")
        if tuple(sorted(set(self.must_preserve))) != self.must_preserve:
            raise ValueError("must_preserve must be unique and deterministic")

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "target_ranges": [item.as_dict() for item in self.target_ranges],
            "expected_behavior_change": self.expected_behavior_change,
            "must_preserve": list(self.must_preserve),
            "planning_evidence_only": True,
            "diff_generated": False,
            "patch_applied": False,
        }


@dataclass(frozen=True, slots=True)
class ValidationCandidate(_RecordMapping):
    kind: str
    target: str
    confidence: str
    test_modification_requires_separate_policy: bool
    write_authority: bool = False
    patch_application_authority: bool = False

    def __post_init__(self) -> None:
        if self.kind not in VALIDATION_KINDS or not self.target.strip():
            raise ValueError("validation candidates require a kind and target")
        if self.confidence not in {"high", "medium", "low", "unknown"}:
            raise ValueError("unknown validation confidence")
        if self.write_authority is not False:
            raise ValueError("validation mapping cannot grant write authority")
        if self.patch_application_authority is not False:
            raise ValueError("validation mapping cannot grant patch authority")

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "confidence": self.confidence,
            "test_modification_requires_separate_policy": (
                self.test_modification_requires_separate_policy
            ),
            "identified_only": True,
            "executed": False,
            "write_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
            "patch_safety_bypassed": False,
        }


@dataclass(frozen=True, slots=True)
class PatchCandidateEvaluation(_RecordMapping):
    path: str
    actionability_score: int
    patchability: PatchabilityScore
    candidate_state: str
    reason: str
    role: str
    patch_role: str
    strategy_id: str
    task_coverage: str | int
    required_paths: tuple[str, ...]
    required_for_coherence: bool
    blast_radius: str
    receipt_freshness: str
    freshness_action: str
    editability: str
    parser_support: str
    understanding_confidence: str
    change_intention: ChangeIntention | None
    validation_candidates: tuple[ValidationCandidate, ...]
    validation_status: str
    warnings: tuple[str, ...]
    redirect_to: str | None = None
    test_modification_requires_separate_policy: bool = False
    write_authority: bool = False
    patch_application_authority: bool = False
    human_approval_required: bool = True

    def __post_init__(self) -> None:
        if self.path != self.patchability.path:
            raise ValueError("candidate and patchability paths must match")
        if not 0 <= self.actionability_score <= 100:
            raise ValueError("actionability score must be bounded from 0 through 100")
        if self.candidate_state not in CANDIDATE_STATES:
            raise ValueError(f"unknown candidate state: {self.candidate_state}")
        if self.blast_radius not in BLAST_RADIUS_LEVELS:
            raise ValueError("unknown blast-radius level")
        if self.receipt_freshness not in {
            "fresh",
            "changed",
            "deleted",
            "replaced",
            "unverifiable",
        }:
            raise ValueError("unknown receipt freshness state")
        if self.validation_status not in {"mapped", "gap"}:
            raise ValueError("validation status must be mapped or gap")
        if self.validation_status == "mapped" and not self.validation_candidates:
            raise ValueError("mapped validation requires at least one candidate")
        if self.validation_status == "gap" and self.validation_candidates:
            raise ValueError("a validation gap cannot expose mapped candidates")
        if self.write_authority is not False:
            raise ValueError("patch candidates never grant write authority")
        if self.patch_application_authority is not False:
            raise ValueError("patch candidates never grant patch authority")
        if self.human_approval_required is not True:
            raise ValueError("patch candidates always require human approval")
        if tuple(sorted(set(self.required_paths))) != self.required_paths:
            raise ValueError("required paths must be deterministic")
        if tuple(sorted(set(self.warnings))) != self.warnings:
            raise ValueError("candidate warnings must be deterministic")

    @property
    def patchability_score(self) -> int:
        return self.patchability.patchability_score

    @property
    def patchability_band(self) -> str:
        return self.patchability.patchability_band

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "path": self.path,
            "actionability_score": self.actionability_score,
            **self.patchability.as_dict(),
            "candidate_state": self.candidate_state,
            "reason": self.reason,
            "role": self.role,
            "patch_role": self.patch_role,
            "strategy_id": self.strategy_id,
            "task_coverage": self.task_coverage,
            "required_paths": list(self.required_paths),
            "required_for_coherence": self.required_for_coherence,
            "blast_radius": self.blast_radius,
            "receipt_freshness": self.receipt_freshness,
            "freshness_action": self.freshness_action,
            "editability": self.editability,
            "parser_support": self.parser_support,
            "understanding_confidence": self.understanding_confidence,
            "AST_claimed": False,
            "dependency_completeness_claimed": False,
            "change_intention": (
                self.change_intention.as_dict()
                if self.change_intention is not None
                else None
            ),
            "validation_candidates": [
                item.as_dict() for item in self.validation_candidates
            ],
            "validation_status": self.validation_status,
            "warnings": list(self.warnings),
            "test_modification_requires_separate_policy": (
                self.test_modification_requires_separate_policy
            ),
            "write_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
            "patch_safety_required": True,
            "patch_safety_bypassed": False,
        }
        if self.redirect_to is not None:
            result["redirect_to"] = self.redirect_to
        return result


@dataclass(frozen=True, slots=True)
class DirectPatchCandidateGateResult(_RecordMapping):
    patch_candidate_status: str
    task_id: str
    operation_id: str
    inventory_identity: str
    files_read: int
    proposed_patch_set: ProposedPatchSet
    evaluations: tuple[PatchCandidateEvaluation, ...]
    targeted_identity_checks: int
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    write_authority: bool = False
    patch_application_authority: bool = False
    human_approval_required: bool = True

    def __post_init__(self) -> None:
        if self.patch_candidate_status != self.proposed_patch_set.status:
            raise ValueError("gate and proposed patch-set statuses must agree")
        if self.write_authority is not False:
            raise ValueError("CTX.PATCH.1 cannot grant write authority")
        if self.patch_application_authority is not False:
            raise ValueError("CTX.PATCH.1 cannot grant patch authority")
        if self.human_approval_required is not True:
            raise ValueError("CTX.PATCH.1 must preserve human approval")
        if self.targeted_identity_checks < 0:
            raise ValueError("identity-check count cannot be negative")

    @property
    def status(self) -> str:
        return self.patch_candidate_status

    def as_dict(self) -> dict[str, Any]:
        plan = self.proposed_patch_set.as_dict()
        return {
            "phase_id": PHASE_ID,
            "context_kind": "direct_file_context",
            "patch_candidate_status": self.patch_candidate_status,
            "status": self.patch_candidate_status,
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "inventory_identity": self.inventory_identity,
            "repository_completeness_claimed": False,
            "files_read": self.files_read,
            "files_evaluated": len(self.evaluations),
            "implementation_candidates": plan["implementation_candidates"],
            "validation_candidates": plan["validation_candidates"],
            "supporting_context": plan["supporting_context"],
            "blocked_candidates": plan["blocked_candidates"],
            "proposed_patch_set": plan,
            "targeted_identity_checks": self.targeted_identity_checks,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "write_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
            "patch_safety_required": True,
            "patch_safety_bypassed": False,
            "test_writing_authority": False,
            "canonical_index_used": False,
            "vector_database_used": False,
            "embeddings_used": False,
            "database_operations": 0,
            "graph_constructed": False,
            "parser_used": False,
            "model_used": False,
            "api_calls_made": False,
            "repository_traversals": 0,
            "production_content_reads": 0,
            "filesystem_writes": 0,
            "patches_generated": 0,
            "patches_applied": 0,
            "validation_commands_executed": 0,
        }


def _value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        if name in value:
            return value[name]
        nested = value.get("capability")
        if isinstance(nested, Mapping) and name in nested:
            return nested[name]
        return default
    return getattr(value, name, default)


def _receipt_value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _validate_serialized_receipt(value: Any) -> None:
    """Validate the no-content receipt contract before trusting a mapping."""

    if isinstance(value, DirectReadReceipt):
        return
    if not isinstance(value, Mapping):
        raise TypeError("direct context receipts must be immutable records or mappings")
    if value.get("read_status") not in {
        "read_complete",
        "read_complete_with_truncation",
    }:
        raise ValueError("direct context contains a non-successful read receipt")
    if value.get("read_mode") not in {
        "full_file",
        "match_windows",
        "explicit_ranges",
        "header_and_matches",
    }:
        raise ValueError("direct context receipt has an invalid read mode")
    for name in ("task_id", "operation_id", "inventory_identity", "path"):
        if not isinstance(value.get(name), str) or not value[name].strip():
            raise ValueError(f"direct context receipt has an invalid {name}")
    if value.get("read_authority_granted") is not True:
        raise ValueError("successful receipt must retain temporary read authority")
    if (
        value.get("write_authority", False) is not False
        or value.get("patch_authority", False) is not False
        or value.get("patch_application_authority", False) is not False
    ):
        raise ValueError("direct context receipt attempts authority escalation")
    identity = value.get("file_identity")
    if not isinstance(identity, Mapping):
        raise ValueError("direct context receipt lacks file identity evidence")
    required_identity = {"device", "inode", "mode", "size_bytes", "modified_ns"}
    if not required_identity <= set(identity):
        raise ValueError("direct context receipt identity is incomplete")

    counter_names = (
        "bytes_scanned",
        "bytes_returned",
        "lines_scanned",
        "lines_returned",
    )
    counters: dict[str, int] = {}
    for name in counter_names:
        raw = value.get(name)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise ValueError(f"direct context receipt has an invalid {name}")
        counters[name] = raw
    if counters["bytes_returned"] > counters["bytes_scanned"] or counters[
        "lines_returned"
    ] > counters["lines_scanned"]:
        raise ValueError("direct context receipt counters are contradictory")

    raw_ranges = value.get("ranges")
    if not isinstance(raw_ranges, (list, tuple)):
        raise ValueError("direct context receipt ranges must be bounded records")
    range_bytes = 0
    range_lines = 0
    normalized_ranges: list[tuple[int, int]] = []
    for item in raw_ranges:
        if not isinstance(item, Mapping):
            raise ValueError("serialized receipt range must be a mapping")
        start = item.get("start_line")
        end = item.get("end_line")
        returned_bytes = item.get("bytes_returned")
        returned_lines = item.get("lines_returned")
        if any(
            isinstance(raw, bool) or not isinstance(raw, int)
            for raw in (start, end, returned_bytes, returned_lines)
        ):
            raise ValueError("serialized receipt range counters must be integers")
        if start <= 0 or end < start or returned_bytes < 0:
            raise ValueError("serialized receipt range bounds are invalid")
        if returned_lines != end - start + 1:
            raise ValueError("serialized receipt range line count is invalid")
        range_bytes += returned_bytes
        range_lines += returned_lines
        normalized_ranges.append((start, end))
    if normalized_ranges != sorted(set(normalized_ranges)):
        raise ValueError("serialized receipt ranges must be deterministic")
    if range_bytes != counters["bytes_returned"] or range_lines != counters[
        "lines_returned"
    ]:
        raise ValueError("serialized receipt range and aggregate counters disagree")

    truncated = value.get("truncated")
    reasons = value.get("truncation_reasons")
    if type(truncated) is not bool or not isinstance(reasons, (list, tuple)):
        raise ValueError("serialized receipt truncation metadata is invalid")
    if tuple(reasons) != tuple(sorted(set(str(item) for item in reasons))):
        raise ValueError("serialized receipt truncation reasons are not deterministic")
    if truncated != bool(reasons):
        raise ValueError("serialized receipt truncation state is contradictory")
    if (value["read_status"] == "read_complete") == truncated:
        raise ValueError("serialized receipt status and truncation state disagree")


def _path_mapping(
    value: Mapping[str, Any] | None,
    *,
    label: str,
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a path-keyed mapping")
    result: dict[str, Any] = {}
    seen: set[str] = set()
    for index, (raw_path, item) in enumerate(value.items()):
        if index >= MAX_SUPPLIED_CANDIDATES:
            raise ValueError(
                f"{label} exceeds the defensive path-mapping limit of "
                f"{MAX_SUPPLIED_CANDIDATES}"
            )
        path = str(raw_path)
        key = path.casefold()
        if key in seen:
            raise ValueError(f"{label} contains duplicate canonical paths")
        seen.add(key)
        result[path] = item
    return result


def _is_test_path(path: str) -> bool:
    pure = PurePosixPath(path)
    parts = {part.casefold() for part in pure.parts}
    name = pure.name.casefold()
    return bool(
        parts & {"test", "tests", "spec", "specs"}
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    )


def _is_configuration(path: str, role: str) -> bool:
    pure = PurePosixPath(path)
    return (
        role.casefold() == "configuration"
        or pure.name.casefold() in CONFIGURATION_NAMES
        or pure.suffix.casefold() in CONFIGURATION_SUFFIXES
    )


def _coerce_target_range(value: Any) -> TargetRange:
    if isinstance(value, TargetRange):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("target ranges must be mappings")
    return TargetRange(
        start_line=value.get("start_line"),
        end_line=value.get("end_line"),
    )


def _coerce_change_intention(value: Any) -> ChangeIntention | None:
    if value is None:
        return None
    if isinstance(value, ChangeIntention):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("change intention must be a mapping")
    forbidden_keys = {
        "diff",
        "patch",
        "applied_diff",
        "commands",
        "hidden_commands",
        "filesystem_write",
    }
    found = forbidden_keys & {str(key).casefold() for key in value}
    if found:
        raise ValueError(
            "change intention contains forbidden patch or command fields: "
            + ", ".join(sorted(found))
        )
    raw_ranges = value.get("target_ranges", ())
    if isinstance(raw_ranges, (str, bytes)):
        raise TypeError("target_ranges must be an iterable")
    captured = tuple(islice(iter(raw_ranges), MAX_TARGET_RANGES + 1))
    if len(captured) > MAX_TARGET_RANGES:
        raise ValueError("change intention exceeds the target-range limit")
    ranges = tuple(sorted({_coerce_target_range(item) for item in captured}))
    raw_preserve = value.get("must_preserve", ())
    if isinstance(raw_preserve, (str, bytes)):
        raise TypeError("must_preserve must be an iterable")
    preserve_values = tuple(
        islice(iter(raw_preserve), MAX_PRESERVATION_ITEMS + 1)
    )
    if len(preserve_values) > MAX_PRESERVATION_ITEMS:
        raise ValueError("change intention exceeds the preservation-item limit")
    preserve = tuple(sorted({str(item).strip() for item in preserve_values if str(item).strip()}))
    return ChangeIntention(
        summary=str(value.get("summary", "")).strip(),
        target_ranges=ranges,
        expected_behavior_change=str(
            value.get("expected_behavior_change", "")
        ).strip(),
        must_preserve=preserve,
    )


def _validation_kind(target: str) -> str:
    lowered = target.casefold()
    if "pytest" in lowered or _is_test_path(target):
        return "pytest"
    if "compile" in lowered:
        return "compile"
    if any(marker in lowered for marker in ("ruff", "flake8", "eslint", "lint")):
        return "linter"
    if any(marker in lowered for marker in ("mypy", "pyright", "typecheck", "type-check")):
        return "type_check"
    if lowered.startswith("manual:"):
        return "manual"
    return "known_validation_command"


def _coerce_validation(value: Any) -> ValidationCandidate:
    if isinstance(value, ValidationCandidate):
        return value
    if isinstance(value, str):
        target = value.strip()
        kind = _validation_kind(target)
        confidence = "high" if kind == "pytest" else "medium"
    elif isinstance(value, Mapping):
        target = str(value.get("target", value.get("path", ""))).strip()
        kind = str(value.get("kind", _validation_kind(target))).strip()
        confidence = str(value.get("confidence", "unknown")).casefold()
    else:
        raise TypeError("validation candidates must be strings or mappings")
    return ValidationCandidate(
        kind=kind,
        target=target,
        confidence=confidence,
        test_modification_requires_separate_policy=_is_test_path(target),
    )


def _coerce_validations(value: Any) -> tuple[ValidationCandidate, ...]:
    if value is None:
        return ()
    raw = (value,) if isinstance(value, (str, bytes, Mapping)) else value
    captured = tuple(islice(iter(raw), MAX_VALIDATION_CANDIDATES + 1))
    if len(captured) > MAX_VALIDATION_CANDIDATES:
        raise ValueError("validation candidates exceed the defensive limit")
    by_key: dict[tuple[str, str], ValidationCandidate] = {}
    for supplied in captured:
        item = _coerce_validation(supplied)
        by_key.setdefault((item.kind, item.target), item)
    return tuple(sorted(by_key.values(), key=lambda item: (item.kind, item.target)))


def _coerce_evidence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, Mapping)):
        if isinstance(value, Mapping) and "kind" in value:
            return (value,)
        raise TypeError("path evidence must be an iterable of evidence records")
    captured = tuple(islice(iter(value), MAX_PATH_EVIDENCE + 1))
    if len(captured) > MAX_PATH_EVIDENCE:
        raise ValueError("path evidence exceeds the defensive limit")
    return captured


def _coerce_risks(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, Mapping, PatchabilityRiskAdjustment)):
        return (value,)
    captured = tuple(islice(iter(value), MAX_PATH_EVIDENCE + 1))
    if len(captured) > MAX_PATH_EVIDENCE:
        raise ValueError("path risks exceed the defensive limit")
    return captured


def _capability(
    path: str,
    candidate: Any,
    entry: Any,
    supplied: FileCapability | Mapping[str, Any] | None,
) -> FileCapability:
    if isinstance(supplied, FileCapability):
        if supplied.path != path:
            raise ValueError("supplied capability path does not match candidate")
        return supplied
    nested = supplied
    if nested is None:
        nested = _value(candidate, "capability")
    size = (
        entry.file_identity.size_bytes
        if entry is not None and entry.file_identity is not None
        else None
    )
    if isinstance(nested, FileCapability):
        if nested.path != path:
            raise ValueError("candidate capability path does not match candidate")
        return nested
    metadata = dict(nested) if isinstance(nested, Mapping) else {}
    metadata["path"] = path
    if metadata.get("size_bytes") is None:
        metadata["size_bytes"] = size
    return classify_file_capability(metadata)


def _actionability_score(candidate: Any) -> int:
    raw = _value(candidate, "actionability_score", 0)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return 0
    return max(0, min(100, raw))


def _receipt_ranges(receipt: Any) -> tuple[TargetRange, ...]:
    raw = _receipt_value(receipt, "ranges", ())
    result: list[TargetRange] = []
    for item in raw:
        if isinstance(item, Mapping):
            result.append(
                TargetRange(int(item["start_line"]), int(item["end_line"]))
            )
        else:
            result.append(
                TargetRange(
                    int(getattr(item, "start_line")),
                    int(getattr(item, "end_line")),
                )
            )
    return tuple(sorted(set(result)))


def _receipt_covers_intention(
    receipt: Any,
    intention: ChangeIntention | None,
) -> bool:
    if intention is None:
        return False
    complete_file = (
        _receipt_value(receipt, "read_mode") == "full_file"
        and not bool(_receipt_value(receipt, "truncated", True))
    )
    if not intention.target_ranges:
        return complete_file
    returned = _receipt_ranges(receipt)
    return all(
        any(
            available.start_line <= target.start_line
            and available.end_line >= target.end_line
            for available in returned
        )
        for target in intention.target_ranges
    )


def _freshness_action(status: str) -> str:
    return {
        "fresh": "candidate_may_be_evaluated",
        "changed": "reread_required",
        "deleted": "candidate_removed",
        "replaced": "security_blocked",
        "unverifiable": "human_review_or_reread_required",
    }[status]


def _freshness(
    receipt: Any | None,
    *,
    current_identity_present: bool,
    current_identity: Any,
) -> ReceiptFreshnessDecision:
    if receipt is None:
        return ReceiptFreshnessDecision(
            "unverifiable", "no successful CTX.READ receipt was supplied", False
        )
    if not current_identity_present:
        return ReceiptFreshnessDecision(
            "unverifiable",
            "no current targeted file identity was supplied",
            False,
        )
    return verify_direct_read_receipt(receipt, current_identity)


def _candidate_sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes, Mapping)):
        raise TypeError("candidates must be an iterable of records")
    captured = tuple(islice(iter(value), MAX_SUPPLIED_CANDIDATES + 1))
    if len(captured) > MAX_SUPPLIED_CANDIDATES:
        raise ValueError(
            f"candidates exceed the defensive limit of {MAX_SUPPLIED_CANDIDATES}"
        )
    return captured


def _candidate_path(candidate: Any) -> str:
    return str(_value(candidate, "path", ""))


def _required_candidate_paths(candidate: Any) -> tuple[str, ...]:
    raw = _value(candidate, "required_paths", ())
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes, Mapping)):
        raise TypeError("candidate required_paths must be an iterable of paths")
    captured = tuple(islice(iter(raw), MAX_REQUIRED_PATHS + 1))
    if len(captured) > MAX_REQUIRED_PATHS:
        raise ValueError("candidate required_paths exceed the defensive limit")
    result = tuple(sorted({str(item) for item in captured if str(item)}))
    if any(not is_safe_repository_relative_path(path) for path in result):
        raise ValueError("candidate required_paths contain an unsafe path")
    return result


def _capabilities_by_path(
    capabilities: Iterable[FileCapability | Mapping[str, Any]] | None,
) -> dict[str, FileCapability | Mapping[str, Any]]:
    if capabilities is None:
        return {}
    if isinstance(capabilities, (str, bytes, Mapping)):
        raise TypeError("capabilities must be an iterable of records")
    result: dict[str, FileCapability | Mapping[str, Any]] = {}
    for item in islice(iter(capabilities), MAX_SUPPLIED_CANDIDATES + 1):
        path = str(_value(item, "path", ""))
        if not path:
            raise ValueError("supplied capability requires a path")
        if path.casefold() in {key.casefold() for key in result}:
            raise ValueError("supplied capabilities contain duplicate paths")
        result[path] = item
    if len(result) > MAX_SUPPLIED_CANDIDATES:
        raise ValueError("supplied capabilities exceed the defensive limit")
    return result


def _validation_evidence(
    validations: tuple[ValidationCandidate, ...],
) -> tuple[Mapping[str, Any], ...]:
    result: list[Mapping[str, Any]] = []
    kinds = {item.kind for item in validations}
    if kinds & {"pytest", "unit_test", "integration_test", "linter", "type_check"}:
        detail = ", ".join(
            item.target
            for item in validations
            if item.kind
            in {"pytest", "unit_test", "integration_test", "linter", "type_check"}
        )
        result.append(
            {
                "kind": "matching_test_or_linter",
                "detail": detail,
                "origin": "ctx_patch_validation_mapping",
                "evidence_id": "validation:matching:" + detail,
            }
        )
    elif validations:
        detail = ", ".join(item.target for item in validations)
        result.append(
            {
                "kind": "validation_coverage",
                "detail": detail,
                "origin": "ctx_patch_validation_mapping",
                "evidence_id": "validation:known:" + detail,
            }
        )
    return tuple(result)


def _validation_from_evidence(
    evidence: tuple[Any, ...],
) -> ValidationCandidate | None:
    matching_kinds = {
        "matching_test_or_linter",
        "matching_test",
        "matching_linter",
        "linter_or_type_check",
    }
    coverage_kinds = {"validation_coverage", "known_validation_command"}
    manual_kinds = {"bounded_manual_verification", "manual_verification_plan"}
    for item in evidence:
        kind = (
            item.kind
            if isinstance(item, PatchabilityEvidence)
            else str(item.get("kind", ""))
            if isinstance(item, Mapping)
            else ""
        )
        if kind not in matching_kinds | coverage_kinds | manual_kinds:
            continue
        detail = (
            item.detail
            if isinstance(item, PatchabilityEvidence)
            else str(item.get("detail", "")).strip()
        )
        if detail:
            resolved_kind = (
                "manual"
                if kind in manual_kinds
                else _validation_kind(detail)
                if kind in matching_kinds
                else "known_validation_command"
            )
            return ValidationCandidate(
                kind=resolved_kind,
                target=detail,
                confidence="low" if resolved_kind == "manual" else "medium",
                test_modification_requires_separate_policy=_is_test_path(detail),
            )
    return None


def _has_validation_patch_evidence(evidence: tuple[Any, ...]) -> bool:
    validation_kinds = {
        "matching_test_or_linter",
        "matching_test",
        "matching_linter",
        "linter_or_type_check",
        "validation_coverage",
        "known_validation_command",
        "bounded_manual_verification",
        "manual_verification_plan",
    }
    return any(
        (
            item.kind
            if isinstance(item, PatchabilityEvidence)
            else str(item.get("kind", ""))
            if isinstance(item, Mapping)
            else ""
        )
        in validation_kinds
        for item in evidence
    )


def _evaluate_candidate(
    candidate: Any,
    *,
    entry: Any,
    receipt: Any | None,
    current_identity_present: bool,
    current_identity: Any,
    expected_task_id: str,
    expected_operation_id: str,
    expected_inventory_identity: str,
    capability: FileCapability,
    evidence: tuple[Any, ...],
    risks: tuple[Any, ...],
    intention: ChangeIntention | None,
    validations: tuple[ValidationCandidate, ...],
    blast_radius: str,
    force_supporting_context: bool = False,
) -> PatchCandidateEvaluation:
    path = _candidate_path(candidate)
    warnings: set[str] = set()
    role = str(_value(candidate, "role", "primary_or_supporting_target"))
    patch_role = str(_value(candidate, "patch_role", ""))
    strategy_id = str(_value(candidate, "strategy_id", "default") or "default")
    task_coverage = _value(candidate, "task_coverage", "unknown")
    required_paths = _required_candidate_paths(candidate)
    required_for_coherence = bool(
        _value(candidate, "required_for_coherence", False)
    )
    test_file = _is_test_path(path) or role.casefold() == "validation"
    configuration = _is_configuration(path, role)

    supplied_validation_status = _value(candidate, "validation_status")
    validation_status_hint = (
        str(supplied_validation_status).casefold()
        if supplied_validation_status is not None
        else None
    )
    if validation_status_hint not in {None, "mapped", "gap"}:
        raise ValueError("candidate validation_status must be mapped or gap")
    validation_inferred_from_evidence = False
    if not validations and validation_status_hint != "gap":
        evidence_validation = _validation_from_evidence(evidence)
        if evidence_validation is not None:
            validations = (evidence_validation,)
            validation_inferred_from_evidence = True
    if validation_status_hint is None:
        validation_status_hint = "mapped" if validations else "gap"
    if validation_status_hint == "gap":
        validations = ()
    validation_status = "mapped" if validations else "gap"
    if validation_status == "gap":
        warnings.add("validation_gap: no validation path is currently known")

    all_evidence = evidence + (
        ()
        if validation_inferred_from_evidence
        or _has_validation_patch_evidence(evidence)
        else _validation_evidence(validations)
    )
    automatic_risks: list[Any] = list(risks)
    if validation_status == "gap":
        automatic_risks.append(
            {"kind": "validation_gap", "detail": "no mapped validation path"}
        )
    if capability.parser_support in {"unsupported", "partial"} or (
        capability.understanding_confidence == "raw_text_only"
    ):
        automatic_risks.append(
            {
                "kind": "weak_parser_or_raw_text_only",
                "detail": "direct context has no complete parser or AST guarantee",
            }
        )
        warnings.add("unsupported or partial parser evidence requires review")
    if configuration:
        automatic_risks.append(
            {
                "kind": "configuration_security_risk",
                "detail": "configuration changes require explicit review",
            }
        )
        warnings.add("configuration candidate requires explicit review")
    automatic_risks.append(
        {
            "kind": f"{blast_radius}_blast_radius",
            "detail": f"blast radius classified as {blast_radius}",
        }
    )
    if bool(_value(candidate, "shared_public_api", False)):
        automatic_risks.append("shared_public_api")
    if bool(_value(candidate, "ambiguous_ownership", False)):
        automatic_risks.append("ambiguous_ownership")
    if bool(_value(candidate, "cross_language_boundary", False)):
        automatic_risks.append("cross_language_boundary")
    if capability.generated or capability.vendor:
        automatic_risks.append("generated_or_derived_file")
    if receipt is not None and bool(_receipt_value(receipt, "truncated", False)):
        automatic_risks.append("stale_or_partial_read")
        warnings.add("partial direct-read evidence requires review")

    hard_zero = capability.editability in {
        "sensitive_requires_approval",
        "outside_scope",
        "opaque",
        "forbidden",
    }
    patchability = calculate_patchability_score(
        path,
        all_evidence,
        risks=automatic_risks,
        hard_blocked=hard_zero,
    )
    positive_kinds = {item.kind for item in patchability.positive_evidence}
    direct_evidence = bool(positive_kinds & DIRECT_QUALIFYING_EVIDENCE)

    freshness = _freshness(
        receipt,
        current_identity_present=current_identity_present,
        current_identity=current_identity,
    )
    freshness_action = _freshness_action(freshness.status)
    receipt_scope_matches = bool(
        receipt is not None
        and _receipt_value(receipt, "read_status")
        in {"read_complete", "read_complete_with_truncation"}
        and _receipt_value(receipt, "task_id") == expected_task_id
        and _receipt_value(receipt, "operation_id") == expected_operation_id
        and _receipt_value(receipt, "inventory_identity")
        == expected_inventory_identity
        and _receipt_value(receipt, "path") == path
    )
    candidate_scope_matches = (
        _value(candidate, "task_id", expected_task_id) == expected_task_id
        and _value(candidate, "operation_id", expected_operation_id)
        == expected_operation_id
    )
    range_covered = (
        _receipt_covers_intention(receipt, intention)
        if receipt is not None and receipt_scope_matches
        else False
    )

    redirect_to: str | None = None
    if not is_safe_repository_relative_path(path) or entry is None:
        state = "outside_scope"
        reason = "path is not a repository-contained supplied inventory member"
    elif not capability.repository_contained:
        state = "outside_scope"
        reason = "capability evidence places the path outside the repository"
    elif capability.symlink_escape:
        state = "forbidden"
        reason = "symlink or replacement ambiguity fails the candidate gate closed"
    elif capability.editability in {"forbidden", "opaque"}:
        state = "forbidden"
        reason = "hard capability policy forbids modification candidacy"
    elif capability.editability == "outside_scope":
        state = "outside_scope"
        reason = "file capability is outside the modification scope"
    elif capability.editability == "sensitive_requires_approval":
        state = "sensitive_blocked"
        reason = "sensitive files remain outside automatic patch candidacy"
    elif capability.editability == "read_only":
        state = "read_only_context"
        reason = "file is relevant read-only supporting context"
    elif capability.editability == "generated_do_not_edit":
        state = "generated_source_redirect"
        redirect_to = capability.authoritative_source
        reason = "generated or derived output must not be edited directly"
        if redirect_to is None:
            warnings.add("generated source redirect has no known authoritative source")
    elif force_supporting_context:
        state = "read_only_context"
        reason = "file was read as supporting context but not supplied as a target"
    elif receipt is None:
        state = "insufficient_evidence"
        reason = "a successful CTX.READ receipt is mandatory"
    elif not receipt_scope_matches or not candidate_scope_matches:
        state = "insufficient_evidence"
        reason = "receipt and candidate task/operation scope do not match"
    elif freshness.status == "replaced":
        state = "forbidden"
        reason = "file replacement is a security-blocked identity change"
    elif freshness.status == "deleted":
        state = "outside_scope"
        reason = "deleted receipt target was removed from candidacy"
    elif freshness.status in {"changed", "unverifiable"}:
        state = "reread_required"
        reason = "only a fresh verified receipt may support patch candidacy"
    elif intention is None:
        state = "insufficient_evidence"
        reason = "no bounded file-level change intention was supplied"
    elif not range_covered:
        state = "insufficient_evidence"
        reason = "direct-read receipt does not cover the bounded target range"
        warnings.add("relevant target range requires a complete or covering reread")
    elif not direct_evidence:
        state = "insufficient_evidence"
        reason = "filename or lexical relevance lacks direct target evidence"
    elif patchability.patchability_score < 65:
        state = "validation_gap" if validation_status == "gap" else "insufficient_evidence"
        reason = "patchability evidence remains below the candidate threshold"
    elif blast_radius in {"high", "critical"}:
        state = "high_blast_radius_review"
        reason = "bounded patch consideration requires blast-radius review"
    elif validation_status == "gap":
        state = "validation_gap"
        reason = "candidate has an explicit validation gap and requires review"
    elif (
        capability.editability == "editable_with_review"
        or capability.parser_support in {"unsupported", "partial"}
        or capability.understanding_confidence == "raw_text_only"
        or configuration
        or blast_radius in {"medium", "unknown"}
        or bool(_value(candidate, "ambiguous_ownership", False))
        or bool(_value(candidate, "shared_public_api", False))
        or bool(_value(candidate, "cross_language_boundary", False))
        or bool(_receipt_value(receipt, "truncated", False))
        or patchability.patchability_score < 80
    ):
        state = "eligible_with_review"
        reason = "direct evidence supports a bounded candidate with explicit review"
    else:
        state = "eligible"
        reason = "fresh direct evidence supports a bounded, validated candidate"

    if blast_radius == "unknown":
        warnings.add("unknown blast radius cannot be treated as low")
    if test_file:
        warnings.add("test modification requires the later test-author policy")
    understanding = (
        "raw_text_only"
        if capability.parser_support == "unsupported"
        else capability.understanding_confidence
    )
    return PatchCandidateEvaluation(
        path=path,
        actionability_score=_actionability_score(candidate),
        patchability=patchability,
        candidate_state=state,
        reason=reason,
        role=role,
        patch_role=patch_role,
        strategy_id=strategy_id,
        task_coverage=task_coverage,
        required_paths=required_paths,
        required_for_coherence=required_for_coherence,
        blast_radius=blast_radius,
        receipt_freshness=freshness.status,
        freshness_action=freshness_action,
        editability=capability.editability,
        parser_support=capability.parser_support,
        understanding_confidence=understanding,
        change_intention=intention,
        validation_candidates=validations,
        validation_status=validation_status,
        warnings=tuple(sorted(warnings)),
        redirect_to=redirect_to,
        test_modification_requires_separate_policy=test_file,
    )


def _empty_plan(status: str, warning: str = "") -> ProposedPatchSet:
    warnings = (warning,) if warning else ()
    # The public planner derives statuses from candidates.  A global contract
    # failure is represented explicitly here without touching any repository.
    return ProposedPatchSet(
        status=status,
        implementation_candidates=(),
        validation_candidates=(),
        supporting_context=(),
        blocked_candidates=(),
        limits=PatchSetLimits(),
        warnings=warnings,
    )


def _blocked_result(
    *,
    task_id: str,
    operation_id: str,
    inventory_identity: str,
    error: str,
) -> DirectPatchCandidateGateResult:
    plan = _empty_plan("blocked", error)
    return DirectPatchCandidateGateResult(
        patch_candidate_status="blocked",
        task_id=task_id or "<invalid-task>",
        operation_id=operation_id or "<invalid-operation>",
        inventory_identity=inventory_identity or "<invalid-inventory>",
        files_read=0,
        proposed_patch_set=plan,
        evaluations=(),
        targeted_identity_checks=0,
        errors=(error,),
    )


def execute_direct_patch_candidate_gate(
    inventory: RepositoryInventory,
    direct_context: Any,
    candidates: Iterable[Any],
    *,
    current_file_identities: Mapping[str, Any] | None = None,
    capabilities: Iterable[FileCapability | Mapping[str, Any]] | None = None,
    patchability_evidence_by_path: Mapping[str, Any] | None = None,
    risk_adjustments_by_path: Mapping[str, Any] | None = None,
    change_intentions_by_path: Mapping[str, Any] | None = None,
    validation_candidates_by_path: Mapping[str, Any] | None = None,
    blast_radius_by_path: Mapping[str, Any] | None = None,
    max_source_files: int = MAX_PROPOSED_SOURCE_FILES,
    max_validation_files: int = MAX_PROPOSED_VALIDATION_FILES,
    max_total_files: int = MAX_PROPOSED_TOTAL_FILES,
    vector_database_available: bool | None = None,
    embedding_provider_enabled: bool | None = None,
    canonical_manifest_available: bool | None = None,
    graph_available: bool | None = None,
    parser_available: bool | None = None,
    model_available: bool | None = None,
) -> DirectPatchCandidateGateResult:
    """Evaluate supplied direct-read evidence and build a no-authority proposal.

    ``current_file_identities`` is the targeted freshness-check seam.  The gate
    never stats paths itself and therefore performs zero repository traversal
    and zero production content reads.
    """

    del vector_database_available
    del embedding_provider_enabled
    del canonical_manifest_available
    del graph_available
    del parser_available
    del model_available

    task_hint = str(_value(direct_context, "task_id", "<invalid-task>"))
    operation_hint = str(
        _value(direct_context, "operation_id", "<invalid-operation>")
    )
    identity_hint = str(
        _value(direct_context, "inventory_identity", "<invalid-inventory>")
    )
    try:
        if not isinstance(inventory, RepositoryInventory):
            raise TypeError("inventory must be a RepositoryInventory")
        task_id = str(_value(direct_context, "task_id", "")).strip()
        operation_id = str(_value(direct_context, "operation_id", "")).strip()
        supplied_inventory_identity = str(
            _value(direct_context, "inventory_identity", "")
        )
        if not task_id or not operation_id:
            raise ValueError("direct context task and operation ids must be nonblank")
        inventory_identity = compute_repository_inventory_identity(inventory)
        if supplied_inventory_identity != inventory_identity:
            raise ValueError("direct context inventory identity does not match task context")
        operation_status = str(
            _value(direct_context, "operation_status", _value(direct_context, "status", ""))
        )
        if operation_status not in {
            "operation_complete",
            "operation_complete_with_partial_reads",
        }:
            raise ValueError("direct context does not represent a completed read operation")
        materialized = _candidate_sequence(candidates)
        candidate_paths = tuple(_candidate_path(item) for item in materialized)
        if any(not path for path in candidate_paths):
            raise ValueError("every supplied candidate requires a nonblank path")
        if len(candidate_paths) != len(
            {path.casefold() for path in candidate_paths}
        ):
            raise ValueError("supplied candidates contain duplicate paths")
        current = _path_mapping(
            current_file_identities, label="current_file_identities"
        )
        evidence_map = _path_mapping(
            patchability_evidence_by_path,
            label="patchability_evidence_by_path",
        )
        risk_map = _path_mapping(
            risk_adjustments_by_path, label="risk_adjustments_by_path"
        )
        intention_map = _path_mapping(
            change_intentions_by_path, label="change_intentions_by_path"
        )
        validation_map = _path_mapping(
            validation_candidates_by_path,
            label="validation_candidates_by_path",
        )
        blast_map = _path_mapping(
            blast_radius_by_path, label="blast_radius_by_path"
        )
        capability_map = _capabilities_by_path(capabilities)
    except (TypeError, ValueError) as exc:
        return _blocked_result(
            task_id=task_hint,
            operation_id=operation_hint,
            inventory_identity=identity_hint,
            error=str(exc),
        )

    entries = {
        entry.relative_path.as_posix(): entry for entry in inventory.entries
    }
    raw_receipts = _value(direct_context, "read_receipts", ())
    if isinstance(raw_receipts, (str, bytes, Mapping)):
        return _blocked_result(
            task_id=task_id,
            operation_id=operation_id,
            inventory_identity=inventory_identity,
            error="direct context read_receipts must be an iterable",
        )
    receipts: dict[str, Any] = {}
    try:
        captured_receipts = tuple(
            islice(iter(raw_receipts), MAX_DIRECT_READ_RECEIPTS + 1)
        )
        if len(captured_receipts) > MAX_DIRECT_READ_RECEIPTS:
            raise ValueError(
                "direct context receipts exceed the CTX.READ file limit"
            )
        for receipt in captured_receipts:
            _validate_serialized_receipt(receipt)
            path = str(_receipt_value(receipt, "path", ""))
            if not path or path.casefold() in {
                existing.casefold() for existing in receipts
            }:
                raise ValueError("direct context receipts contain invalid duplicate paths")
            receipts[path] = receipt
    except (TypeError, ValueError) as exc:
        return _blocked_result(
            task_id=task_id,
            operation_id=operation_id,
            inventory_identity=inventory_identity,
            error=str(exc),
        )

    supplied_by_path = {_candidate_path(item): item for item in materialized}
    evaluation_inputs: list[tuple[Any, bool]] = [
        (item, False) for item in materialized
    ]
    # A successful read not carried forward by CTX.SELECT remains visible as
    # supporting context rather than becoming an implicit patch target.
    for path in sorted(set(receipts) - set(supplied_by_path)):
        evaluation_inputs.append(
            (
                {
                    "path": path,
                    "actionability_score": 0,
                    "role": "supporting_context",
                    "patch_role": "",
                },
                True,
            )
        )

    evaluations: list[PatchCandidateEvaluation] = []
    top_warnings: set[str] = set()
    identity_checks = 0
    try:
        for candidate, force_supporting in evaluation_inputs:
            path = _candidate_path(candidate)
            entry = entries.get(path)
            receipt = receipts.get(path)
            supplied_capability = capability_map.get(path)
            resolved_capability = _capability(
                path, candidate, entry, supplied_capability
            )
            raw_evidence = (
                evidence_map[path]
                if path in evidence_map
                else _value(
                    candidate,
                    "patchability_evidence",
                    _value(
                        candidate,
                        "patch_evidence",
                        _value(candidate, "positive_evidence", ()),
                    ),
                )
            )
            raw_risks = (
                risk_map[path]
                if path in risk_map
                else _value(
                    candidate,
                    "patchability_risks",
                    _value(candidate, "risk_adjustments", ()),
                )
            )
            raw_intention = (
                intention_map[path]
                if path in intention_map
                else _value(candidate, "change_intention")
            )
            raw_validations = (
                validation_map[path]
                if path in validation_map
                else _value(candidate, "validation_candidates", ())
            )
            blast_raw = (
                blast_map[path]
                if path in blast_map
                else _value(candidate, "blast_radius", "unknown")
            )
            blast = str(blast_raw).casefold()
            if blast not in BLAST_RADIUS_LEVELS:
                blast = "unknown"
                top_warnings.add(f"{path}: invalid blast-radius evidence became unknown")
            try:
                intention = _coerce_change_intention(raw_intention)
            except (TypeError, ValueError) as exc:
                intention = None
                top_warnings.add(f"{path}: invalid change intention: {exc}")
            try:
                validations = _coerce_validations(raw_validations)
            except (TypeError, ValueError) as exc:
                validations = ()
                top_warnings.add(f"{path}: invalid validation mapping: {exc}")
            evaluation = _evaluate_candidate(
                candidate,
                entry=entry,
                receipt=receipt,
                current_identity_present=path in current,
                current_identity=current.get(path),
                expected_task_id=task_id,
                expected_operation_id=operation_id,
                expected_inventory_identity=inventory_identity,
                capability=resolved_capability,
                evidence=_coerce_evidence(raw_evidence),
                risks=_coerce_risks(raw_risks),
                intention=intention,
                validations=validations,
                blast_radius=blast,
                force_supporting_context=force_supporting,
            )
            evaluations.append(evaluation)
            if receipt is not None:
                identity_checks += 1
            for warning in evaluation.warnings:
                top_warnings.add(f"{path}: {warning}")
    except (TypeError, ValueError) as exc:
        return _blocked_result(
            task_id=task_id,
            operation_id=operation_id,
            inventory_identity=inventory_identity,
            error=str(exc),
        )

    try:
        plan = build_proposed_patch_set(
            evaluations,
            max_source_files=max_source_files,
            max_validation_files=max_validation_files,
            max_total_files=max_total_files,
        )
    except (TypeError, ValueError) as exc:
        return _blocked_result(
            task_id=task_id,
            operation_id=operation_id,
            inventory_identity=inventory_identity,
            error=str(exc),
        )
    proposed_paths = set(plan.paths)
    if not proposed_paths <= set(receipts):
        return _blocked_result(
            task_id=task_id,
            operation_id=operation_id,
            inventory_identity=inventory_identity,
            error="internal invariant failed: patch candidates must be a subset of reads",
        )
    if any(
        item.receipt_freshness != "fresh"
        for item in plan.implementation_candidates + plan.validation_candidates
    ):
        return _blocked_result(
            task_id=task_id,
            operation_id=operation_id,
            inventory_identity=inventory_identity,
            error="internal invariant failed: proposed candidates must have fresh receipts",
        )
    top_warnings.update(plan.warnings)
    return DirectPatchCandidateGateResult(
        patch_candidate_status=plan.status,
        task_id=task_id,
        operation_id=operation_id,
        inventory_identity=inventory_identity,
        files_read=len(receipts),
        proposed_patch_set=plan,
        evaluations=tuple(sorted(evaluations, key=lambda item: item.path)),
        targeted_identity_checks=identity_checks,
        warnings=tuple(sorted(top_warnings))[:MAX_WARNINGS],
    )


# Stable public aliases used by callers with different orchestration wording.
evaluate_direct_patch_candidates = execute_direct_patch_candidate_gate
run_direct_patch_candidate_gate = execute_direct_patch_candidate_gate
build_direct_patch_candidate_result = execute_direct_patch_candidate_gate
