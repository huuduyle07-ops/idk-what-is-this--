"""Pure, fail-closed completion evidence for canonical repository indexing.

INDEX.1D.2C separates source processing, durable persistence, scope
reconciliation, and non-authoritative outputs.  Nothing in this module scans a
repository, calls a model, accesses a database, or reads/writes a manifest.

The production indexer may emit this evidence additively, but applied-manifest
commit wiring remains a later phase.  Consequently a classified completion can
permit a manifest commit while its own ``trusted_current_claim_allowed`` field
remains false.  A separate pure gate requires matching applied-manifest
evidence before repository intelligence may be called current.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
import os
from pathlib import PurePosixPath
import re
from typing import Any

from core.credential_redaction import redact_credentials
from core.repository_identity_state import (
    IDENTITY_STATUS_CONFIRMED,
    IDENTITY_STATUSES,
    RepositoryIdentityState,
    derive_canonical_identity_permissions,
    validate_repository_identity_state,
)


PHASE_ID = "INDEX.1D.2C"
PHASE_TITLE = "Honest Persistence Completion Contract"
COMPLETION_CONTRACT_VERSION = "index_completion_v1"

STATUS_COMPLETE = "complete"
STATUS_COMPLETE_WITH_WARNINGS = "complete_with_warnings"
STATUS_PROCESSING_FAILED = "processing_failed"
STATUS_PERSISTENCE_FAILED = "persistence_failed"
STATUS_RECONCILIATION_FAILED = "reconciliation_failed"
STATUS_IDENTITY_BLOCKED = "identity_blocked"
STATUS_PERSISTENCE_DISABLED = "persistence_disabled"
STATUS_PERSISTENCE_NOT_ATTEMPTED = "persistence_not_attempted"
STATUS_AUXILIARY_FAILED = "auxiliary_failed"
STATUS_INVALID_COMPLETION_EVIDENCE = "invalid_completion_evidence"
COMPLETION_STATUSES = (
    STATUS_COMPLETE,
    STATUS_COMPLETE_WITH_WARNINGS,
    STATUS_PROCESSING_FAILED,
    STATUS_PERSISTENCE_FAILED,
    STATUS_RECONCILIATION_FAILED,
    STATUS_IDENTITY_BLOCKED,
    STATUS_PERSISTENCE_DISABLED,
    STATUS_PERSISTENCE_NOT_ATTEMPTED,
    STATUS_AUXILIARY_FAILED,
    STATUS_INVALID_COMPLETION_EVIDENCE,
)

FILE_ACTION_ADDED = "added"
FILE_ACTION_MODIFIED = "modified"
FILE_ACTION_DELETED = "deleted"
FILE_ACTION_UNCHANGED = "unchanged"
FILE_ACTION_FULL_REFRESH = "full_refresh"
FILE_ACTION_NOT_REQUIRED = "not_required"
FILE_ACTIONS = (
    FILE_ACTION_ADDED,
    FILE_ACTION_MODIFIED,
    FILE_ACTION_DELETED,
    FILE_ACTION_UNCHANGED,
    FILE_ACTION_FULL_REFRESH,
    FILE_ACTION_NOT_REQUIRED,
)

PROCESSING_STATUS_NOT_REQUIRED = "not_required"
PROCESSING_STATUS_PENDING = "pending"
PROCESSING_STATUS_PROCESSED = "processed"
PROCESSING_STATUS_PARSE_FAILED = "parse_failed"
PROCESSING_STATUS_BLOCKED = "blocked"
PROCESSING_STATUSES = (
    PROCESSING_STATUS_NOT_REQUIRED,
    PROCESSING_STATUS_PENDING,
    PROCESSING_STATUS_PROCESSED,
    PROCESSING_STATUS_PARSE_FAILED,
    PROCESSING_STATUS_BLOCKED,
)

EMBEDDING_STATUS_NOT_REQUIRED = "not_required"
EMBEDDING_STATUS_PENDING = "pending"
EMBEDDING_STATUS_EMBEDDED = "embedded"
EMBEDDING_STATUS_FAILED = "embedding_failed"
EMBEDDING_STATUS_BLOCKED = "blocked"
EMBEDDING_STATUSES = (
    EMBEDDING_STATUS_NOT_REQUIRED,
    EMBEDDING_STATUS_PENDING,
    EMBEDDING_STATUS_EMBEDDED,
    EMBEDDING_STATUS_FAILED,
    EMBEDDING_STATUS_BLOCKED,
)

FILE_PERSISTENCE_NOT_REQUIRED = "not_required"
FILE_PERSISTENCE_PENDING = "pending"
FILE_PERSISTENCE_PERSISTED = "persisted"
FILE_PERSISTENCE_DELETED = "deleted"
FILE_PERSISTENCE_SKIPPED_UNCHANGED = "skipped_unchanged"
FILE_PERSISTENCE_PARSE_FAILED = "parse_failed"
FILE_PERSISTENCE_EMBEDDING_FAILED = "embedding_failed"
FILE_PERSISTENCE_REPLACEMENT_FAILED = "replacement_failed"
FILE_PERSISTENCE_DELETION_FAILED = "deletion_failed"
FILE_PERSISTENCE_BLOCKED = "blocked"
FILE_PERSISTENCE_STATUSES = (
    FILE_PERSISTENCE_NOT_REQUIRED,
    FILE_PERSISTENCE_PENDING,
    FILE_PERSISTENCE_PERSISTED,
    FILE_PERSISTENCE_DELETED,
    FILE_PERSISTENCE_SKIPPED_UNCHANGED,
    FILE_PERSISTENCE_PARSE_FAILED,
    FILE_PERSISTENCE_EMBEDDING_FAILED,
    FILE_PERSISTENCE_REPLACEMENT_FAILED,
    FILE_PERSISTENCE_DELETION_FAILED,
    FILE_PERSISTENCE_BLOCKED,
)
FILE_FAILURE_STATUSES = frozenset({
    FILE_PERSISTENCE_PARSE_FAILED,
    FILE_PERSISTENCE_EMBEDDING_FAILED,
    FILE_PERSISTENCE_REPLACEMENT_FAILED,
    FILE_PERSISTENCE_DELETION_FAILED,
    FILE_PERSISTENCE_BLOCKED,
})

AUXILIARY_AUTHORITY_AUTHORITATIVE = (
    "authoritative_completion_dependency"
)
AUXILIARY_AUTHORITY_OUTPUT = "auxiliary_output"
AUXILIARY_AUTHORITY_UNKNOWN = "unknown"
AUXILIARY_AUTHORITIES = (
    AUXILIARY_AUTHORITY_AUTHORITATIVE,
    AUXILIARY_AUTHORITY_OUTPUT,
    AUXILIARY_AUTHORITY_UNKNOWN,
)

MANIFEST_GATE_ALLOWED = "manifest_advance_allowed"
MANIFEST_GATE_IDENTITY_BLOCKED = "identity_blocked"
MANIFEST_GATE_COMPLETION_BLOCKED = "completion_blocked"
MANIFEST_GATE_INVALID = "invalid_completion_evidence"

CURRENT_CLAIM_ALLOWED = "trusted_current_claim_allowed"
CURRENT_CLAIM_IDENTITY_BLOCKED = "identity_blocked"
CURRENT_CLAIM_COMPLETION_BLOCKED = "completion_blocked"
CURRENT_CLAIM_MANIFEST_NOT_COMMITTED = "manifest_not_committed"
CURRENT_CLAIM_RUN_MISMATCH = "manifest_run_mismatch"
CURRENT_CLAIM_STATE_MISMATCH = "manifest_state_mismatch"
CURRENT_CLAIM_INVALID = "invalid_current_claim_evidence"

MAX_ERROR_MESSAGE_LENGTH = 4_000
MAX_REASON_LENGTH = 1_000
_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CLASSIFIER_TOKEN = object()
_IDENTITY_EVIDENCE_TOKEN = object()


class _RecordMapping(Mapping[str, Any]):
    """Small immutable-record compatibility surface."""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())


def _is_exact_data_tree(value: Any) -> bool:
    value_type = type(value)
    if value_type in {type(None), bool, int, str}:
        return True
    if value_type is list:
        return all(_is_exact_data_tree(item) for item in value)
    if value_type is dict:
        return all(
            type(key) is str and _is_exact_data_tree(item)
            for key, item in value.items()
        )
    return False


def _type_strict_data_equal(expected: Any, actual: Any) -> bool:
    if type(expected) is not type(actual):
        return False
    value_type = type(expected)
    if value_type in {type(None), bool, int, str}:
        return expected == actual
    if value_type is list:
        return len(expected) == len(actual) and all(
            _type_strict_data_equal(left, right)
            for left, right in zip(expected, actual)
        )
    if value_type is dict:
        if (
            not _is_exact_data_tree(expected)
            or not _is_exact_data_tree(actual)
            or expected.keys() != actual.keys()
        ):
            return False
        return all(
            _type_strict_data_equal(expected[key], actual[key])
            for key in expected
        )
    return False


@dataclass(frozen=True)
class IdentityCompletionEvidence(_RecordMapping):
    """Identity-only evidence supplied to the pure classifier.

    The manifest and current-claim gates do not trust this compact record.
    They revalidate a full ``RepositoryIdentityState`` independently.
    """

    identity_status: str
    canonical_mutation_allowed: bool
    reconciliation_allowed: bool
    applied_manifest_advance_allowed: bool
    repository_id: str | None = None
    active_index_scope: str | None = None
    architecture_epoch: int | None = None
    state_revision: int | None = None
    _identity_token: object = field(
        default=None,
        repr=False,
        compare=False,
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity_status": self.identity_status,
            "canonical_mutation_allowed": (
                self.canonical_mutation_allowed
            ),
            "reconciliation_allowed": self.reconciliation_allowed,
            "applied_manifest_advance_allowed": (
                self.applied_manifest_advance_allowed
            ),
            "repository_id": self.repository_id,
            "active_index_scope": self.active_index_scope,
            "architecture_epoch": self.architecture_epoch,
            "state_revision": self.state_revision,
        }


@dataclass(frozen=True)
class ProcessingEvidence(_RecordMapping):
    attempted: bool
    ok: bool
    failed_files: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    error_category: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "ok": self.ok,
            "failed_files": list(self.failed_files),
            "warnings": list(self.warnings),
            "error_category": self.error_category,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class FilePersistenceEvidence(_RecordMapping):
    file_path: str
    action: str
    processing_status: str
    embedding_status: str
    persistence_status: str
    embedding_required: bool = False
    error_category: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "action": self.action,
            "processing_status": self.processing_status,
            "embedding_status": self.embedding_status,
            "persistence_status": self.persistence_status,
            "embedding_required": self.embedding_required,
            "error_category": self.error_category,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class PersistenceEvidence(_RecordMapping):
    required: bool
    enabled: bool
    attempted: bool
    ok: bool
    index_scope: str | None = None
    files: tuple[FilePersistenceEvidence, ...] = ()
    required_files: tuple[str, ...] = ()
    aborted_after_failure: bool = False
    unattempted_required_files: tuple[str, ...] = ()
    failure_stage: str | None = None
    error_category: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "enabled": self.enabled,
            "attempted": self.attempted,
            "ok": self.ok,
            "index_scope": self.index_scope,
            "files": [item.to_dict() for item in self.files],
            "required_files": list(self.required_files),
            "aborted_after_failure": self.aborted_after_failure,
            "unattempted_required_files": list(
                self.unattempted_required_files
            ),
            "failure_stage": self.failure_stage,
            "error_category": self.error_category,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class ReconciliationEvidence(_RecordMapping):
    required: bool
    attempted: bool
    ok: bool
    index_scope: str | None = None
    deleted_units: int = 0
    deleted_dependencies: int = 0
    preserved_external_targets: int = 0
    skipped_reason: str | None = None
    error_category: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "attempted": self.attempted,
            "ok": self.ok,
            "index_scope": self.index_scope,
            "deleted_units": self.deleted_units,
            "deleted_dependencies": self.deleted_dependencies,
            "preserved_external_targets": (
                self.preserved_external_targets
            ),
            "skipped_reason": self.skipped_reason,
            "error_category": self.error_category,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class AuxiliaryEvidence(_RecordMapping):
    component: str
    authority: str
    attempted: bool
    ok: bool
    error_category: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "authority": self.authority,
            "attempted": self.attempted,
            "ok": self.ok,
            "error_category": self.error_category,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class IndexCompletionDecision(_RecordMapping):
    processing_ok: bool
    persistence_required: bool
    persistence_attempted: bool
    persistence_ok: bool
    reconciliation_required: bool
    reconciliation_attempted: bool
    reconciliation_ok: bool
    auxiliary_graph_ok: bool | None
    trusted_completion: bool
    manifest_advance_allowed: bool
    trusted_current_claim_allowed: bool
    current_claim_requires_manifest_commit: bool
    status: str
    failure_stage: str | None
    failed_files: tuple[str, ...]
    warnings: tuple[str, ...]
    reasons: tuple[str, ...]
    identity_status: str
    repository_id: str | None
    active_index_scope: str | None
    architecture_epoch: int | None
    identity_state_revision: int | None
    completion_run_id: str | None
    observed_state_id: str | None
    persistence_aborted_after_failure: bool
    unattempted_required_files: tuple[str, ...]
    reconciliation_skipped_reason: str | None
    file_outcomes: tuple[FilePersistenceEvidence, ...]
    auxiliary_outcomes: tuple[AuxiliaryEvidence, ...]
    evidence_validated: bool
    contract_version: str = COMPLETION_CONTRACT_VERSION
    _identity_source: object = field(
        default=None,
        repr=False,
        compare=False,
    )
    _processing_source: object = field(
        default=None,
        repr=False,
        compare=False,
    )
    _persistence_source: object = field(
        default=None,
        repr=False,
        compare=False,
    )
    _reconciliation_source: object = field(
        default=None,
        repr=False,
        compare=False,
    )
    _auxiliary_source: object = field(
        default=None,
        repr=False,
        compare=False,
    )
    _completion_run_id_source: object = field(
        default=None,
        repr=False,
        compare=False,
    )
    _observed_state_id_source: object = field(
        default=None,
        repr=False,
        compare=False,
    )
    _classifier_token: object = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self._classifier_token is not _CLASSIFIER_TOKEN:
            raise ValueError(
                "IndexCompletionDecision must be produced by "
                "classify_index_completion"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "status": self.status,
            "identity_status": self.identity_status,
            "repository_id": self.repository_id,
            "active_index_scope": self.active_index_scope,
            "architecture_epoch": self.architecture_epoch,
            "identity_state_revision": self.identity_state_revision,
            "completion_run_id": self.completion_run_id,
            "observed_state_id": self.observed_state_id,
            "processing_ok": self.processing_ok,
            "persistence_required": self.persistence_required,
            "persistence_attempted": self.persistence_attempted,
            "persistence_ok": self.persistence_ok,
            "persistence_aborted_after_failure": (
                self.persistence_aborted_after_failure
            ),
            "unattempted_required_files": list(
                self.unattempted_required_files
            ),
            "reconciliation_required": self.reconciliation_required,
            "reconciliation_attempted": (
                self.reconciliation_attempted
            ),
            "reconciliation_ok": self.reconciliation_ok,
            "reconciliation_skipped_reason": (
                self.reconciliation_skipped_reason
            ),
            "auxiliary_graph_ok": self.auxiliary_graph_ok,
            "trusted_completion": self.trusted_completion,
            "manifest_advance_allowed": (
                self.manifest_advance_allowed
            ),
            "trusted_current_claim_allowed": (
                self.trusted_current_claim_allowed
            ),
            "current_claim_requires_manifest_commit": (
                self.current_claim_requires_manifest_commit
            ),
            "failure_stage": self.failure_stage,
            "failed_files": list(self.failed_files),
            "warnings": list(self.warnings),
            "reasons": list(self.reasons),
            "file_outcomes": [
                item.to_dict() for item in self.file_outcomes
            ],
            "auxiliary_outcomes": [
                item.to_dict() for item in self.auxiliary_outcomes
            ],
            "evidence_validated": self.evidence_validated,
        }


@dataclass(frozen=True)
class ManifestAdvanceDecision(_RecordMapping):
    allowed: bool
    status: str
    reason: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "reason": self.reason,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class AppliedManifestEvidence(_RecordMapping):
    """Caller-supplied proof of one completed applied-manifest commit."""

    committed: bool
    completion_run_id: str
    applied_manifest_run_id: str
    observed_state_id: str
    applied_state_id: str
    repository_id: str | None = None
    active_index_scope: str | None = None
    architecture_epoch: int | None = None
    identity_state_revision: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "committed": self.committed,
            "completion_run_id": self.completion_run_id,
            "applied_manifest_run_id": self.applied_manifest_run_id,
            "observed_state_id": self.observed_state_id,
            "applied_state_id": self.applied_state_id,
            "repository_id": self.repository_id,
            "active_index_scope": self.active_index_scope,
            "architecture_epoch": self.architecture_epoch,
            "identity_state_revision": self.identity_state_revision,
        }


@dataclass(frozen=True)
class TrustedCurrentClaimDecision(_RecordMapping):
    allowed: bool
    status: str
    reason: str
    completion_run_id: str | None
    applied_manifest_run_id: str | None
    observed_state_id: str | None
    applied_state_id: str | None
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "reason": self.reason,
            "completion_run_id": self.completion_run_id,
            "applied_manifest_run_id": self.applied_manifest_run_id,
            "observed_state_id": self.observed_state_id,
            "applied_state_id": self.applied_state_id,
            "reasons": list(self.reasons),
        }


def identity_completion_evidence(
    identity_state: (
        RepositoryIdentityState | Mapping[str, Any] | None
    ),
) -> IdentityCompletionEvidence:
    """Derive compact classifier evidence from a full identity record."""
    if isinstance(identity_state, RepositoryIdentityState):
        status = identity_state.identity_status
    elif isinstance(identity_state, Mapping):
        raw_status = identity_state.get("identity_status")
        status = raw_status if isinstance(raw_status, str) else "blocked"
    else:
        status = "blocked"

    permissions = derive_canonical_identity_permissions(
        identity_state
    )
    return IdentityCompletionEvidence(
        identity_status=status,
        canonical_mutation_allowed=(
            permissions.canonical_build_allowed
            or permissions.canonical_refresh_allowed
        ),
        reconciliation_allowed=permissions.reconciliation_allowed,
        applied_manifest_advance_allowed=(
            permissions.applied_manifest_advance_allowed
        ),
        repository_id=(
            identity_state.repository_id
            if isinstance(identity_state, RepositoryIdentityState)
            else None
        ),
        active_index_scope=(
            identity_state.active_index_scope
            if isinstance(identity_state, RepositoryIdentityState)
            else None
        ),
        architecture_epoch=(
            identity_state.architecture_epoch
            if isinstance(identity_state, RepositoryIdentityState)
            else None
        ),
        state_revision=(
            identity_state.state_revision
            if isinstance(identity_state, RepositoryIdentityState)
            else None
        ),
        _identity_token=_IDENTITY_EVIDENCE_TOKEN,
    )


def _safe_text(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
    allow_none: bool = True,
    maximum: int = MAX_REASON_LENGTH,
    require_pre_redacted: bool = False,
) -> str | None:
    if value is None:
        if allow_none:
            return None
        errors.append(f"{field_name} is required")
        return ""
    if not isinstance(value, str):
        errors.append(f"{field_name} must be text")
        value = str(value)
    sanitized = redact_credentials(value).strip()
    if require_pre_redacted and sanitized != value.strip():
        errors.append(
            f"{field_name} must already be credential-redacted"
        )
    if not sanitized and not allow_none:
        errors.append(f"{field_name} must not be blank")
    if len(sanitized) > maximum:
        errors.append(f"{field_name} exceeds {maximum} characters")
        sanitized = sanitized[:maximum]
    if _CONTROL_CHARACTER_RE.search(sanitized):
        errors.append(f"{field_name} contains unsafe control characters")
        sanitized = _CONTROL_CHARACTER_RE.sub("", sanitized)
    return sanitized or None


def _strict_bool(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
) -> bool:
    if type(value) is not bool:
        errors.append(f"{field_name} must be a boolean")
        return False
    return value


def _nonnegative_int(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
) -> int:
    if type(value) is not int or value < 0:
        errors.append(f"{field_name} must be a non-negative integer")
        return 0
    return value


def _sequence(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
        value,
        Sequence,
    ):
        errors.append(f"{field_name} must be a sequence")
        return ()
    return tuple(value)


def _record_values(
    value: Any,
    *,
    record_type: type,
    fields: tuple[str, ...],
    errors: list[str],
    field_name: str,
) -> dict[str, Any]:
    if isinstance(value, record_type):
        return {name: getattr(value, name) for name in fields}
    if not isinstance(value, Mapping):
        errors.append(
            f"{field_name} must be {record_type.__name__} or a mapping"
        )
        return {}
    unknown = set(value) - set(fields)
    if unknown:
        errors.append(
            f"{field_name} contains unknown fields: "
            + ", ".join(sorted(str(item) for item in unknown))
        )
    return {name: value.get(name) for name in fields}


def _normalize_path(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
) -> str:
    path = _safe_text(
        value,
        field_name=field_name,
        errors=errors,
        allow_none=False,
        maximum=1_024,
    )
    if not path:
        return ""
    candidate = PurePosixPath(path)
    if (
        "\\" in path
        or ":" in path
        or candidate.is_absolute()
        or not candidate.parts
        or any(part in {"", ".", ".."} for part in candidate.parts)
        or candidate.as_posix() != path
    ):
        errors.append(
            f"{field_name} must be a normalized safe relative path"
        )
    return path


def _path_comparison_key(path: str) -> str:
    return path.casefold() if os.name == "nt" else path


def _normalize_paths(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
) -> tuple[str, ...]:
    paths = [
        _normalize_path(
            item,
            field_name=f"{field_name}[{index}]",
            errors=errors,
        )
        for index, item in enumerate(
            _sequence(value, field_name=field_name, errors=errors)
        )
    ]
    nonblank = [item for item in paths if item]
    if len(
        {_path_comparison_key(item) for item in nonblank}
    ) != len(nonblank):
        errors.append(f"{field_name} contains duplicate file paths")
    return tuple(sorted(set(nonblank)))


def _normalize_messages(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
) -> tuple[str, ...]:
    messages: set[str] = set()
    for index, item in enumerate(
        _sequence(value, field_name=field_name, errors=errors)
    ):
        safe = _safe_text(
            item,
            field_name=f"{field_name}[{index}]",
            errors=errors,
            allow_none=False,
            require_pre_redacted=True,
        )
        if safe:
            messages.add(safe)
    return tuple(sorted(messages))


def _extend_safe_validation_reasons(
    target: list[str],
    reasons: Sequence[Any],
    *,
    prefix: str,
) -> None:
    for index, reason in enumerate(reasons):
        sanitization_errors: list[str] = []
        safe_reason = _safe_text(
            reason,
            field_name=f"{prefix}.validation_errors[{index}]",
            errors=sanitization_errors,
            allow_none=False,
            maximum=MAX_REASON_LENGTH,
            require_pre_redacted=True,
        )
        target.extend(sanitization_errors)
        if safe_reason:
            target.append(f"{prefix}: {safe_reason}")


def _normalize_identity(
    value: Any,
    errors: list[str],
) -> IdentityCompletionEvidence:
    if isinstance(value, RepositoryIdentityState):
        try:
            identity_payload = value.to_dict()
        except Exception:
            identity_payload = None
            errors.append(
                "identity_state could not be represented as immutable "
                "evidence"
            )
        if not _is_exact_data_tree(identity_payload):
            errors.append(
                "identity_state must contain only exact built-in "
                "evidence values"
            )
        try:
            validation = validate_repository_identity_state(value)
        except Exception:
            validation = None
            errors.append(
                "identity_state structural validation raised an error"
            )
        if validation is not None and not validation.valid:
            _extend_safe_validation_reasons(
                errors,
                validation.errors
                or ("identity state is structurally invalid",),
                prefix="identity_state",
            )
        try:
            evidence = identity_completion_evidence(value)
        except Exception:
            errors.append(
                "identity permissions could not be derived safely"
            )
            evidence = identity_completion_evidence(None)
    elif value is None:
        evidence = identity_completion_evidence(None)
    else:
        errors.append(
            "identity_state must be a full RepositoryIdentityState"
        )
        evidence = identity_completion_evidence(None)

    status = evidence.identity_status
    if type(status) is not str or status not in IDENTITY_STATUSES:
        errors.append("identity_status is not a stable identity status")
        status = "blocked"
    mutation = _strict_bool(
        evidence.canonical_mutation_allowed,
        field_name="identity.canonical_mutation_allowed",
        errors=errors,
    )
    reconciliation = _strict_bool(
        evidence.reconciliation_allowed,
        field_name="identity.reconciliation_allowed",
        errors=errors,
    )
    manifest = _strict_bool(
        evidence.applied_manifest_advance_allowed,
        field_name="identity.applied_manifest_advance_allowed",
        errors=errors,
    )
    if status != IDENTITY_STATUS_CONFIRMED and any(
        (mutation, reconciliation, manifest)
    ):
        errors.append(
            "non-confirmed identity cannot grant canonical permissions"
        )
    repository_id = evidence.repository_id
    if (
        repository_id is not None
        and type(repository_id) is not str
    ):
        errors.append("identity.repository_id must be exact text")
        repository_id = None
    active_index_scope = evidence.active_index_scope
    if (
        active_index_scope is not None
        and type(active_index_scope) is not str
    ):
        errors.append("identity.active_index_scope must be exact text")
        active_index_scope = None
    architecture_epoch = evidence.architecture_epoch
    if (
        architecture_epoch is not None
        and (
            type(architecture_epoch) is not int
            or architecture_epoch <= 0
        )
    ):
        errors.append(
            "identity.architecture_epoch must be a positive integer or "
            "None"
        )
        architecture_epoch = None
    state_revision = evidence.state_revision
    if (
        state_revision is not None
        and (
            type(state_revision) is not int
            or state_revision < 0
        )
    ):
        errors.append(
            "identity.state_revision must be a non-negative integer or "
            "None"
        )
        state_revision = None
    return IdentityCompletionEvidence(
        identity_status=status,
        canonical_mutation_allowed=mutation,
        reconciliation_allowed=reconciliation,
        applied_manifest_advance_allowed=manifest,
        repository_id=repository_id,
        active_index_scope=active_index_scope,
        architecture_epoch=architecture_epoch,
        state_revision=state_revision,
        _identity_token=_IDENTITY_EVIDENCE_TOKEN,
    )


def _normalize_processing(
    value: Any,
    errors: list[str],
) -> ProcessingEvidence:
    fields = (
        "attempted",
        "ok",
        "failed_files",
        "warnings",
        "error_category",
        "error_message",
    )
    values = _record_values(
        value,
        record_type=ProcessingEvidence,
        fields=fields,
        errors=errors,
        field_name="processing",
    )
    attempted = _strict_bool(
        values.get("attempted"),
        field_name="processing.attempted",
        errors=errors,
    )
    ok = _strict_bool(
        values.get("ok"),
        field_name="processing.ok",
        errors=errors,
    )
    failed_files = _normalize_paths(
        values.get("failed_files", ()),
        field_name="processing.failed_files",
        errors=errors,
    )
    warnings = _normalize_messages(
        values.get("warnings", ()),
        field_name="processing.warnings",
        errors=errors,
    )
    error_category = _safe_text(
        values.get("error_category"),
        field_name="processing.error_category",
        errors=errors,
    )
    error_message = _safe_text(
        values.get("error_message"),
        field_name="processing.error_message",
        errors=errors,
        maximum=MAX_ERROR_MESSAGE_LENGTH,
        require_pre_redacted=True,
    )
    if ok and not attempted:
        errors.append("processing ok=true requires attempted=true")
    if ok and failed_files:
        errors.append(
            "processing ok=true contradicts non-empty failed_files"
        )
    if ok and (
        error_category is not None or error_message is not None
    ):
        errors.append(
            "successful processing cannot contain aggregate errors"
        )
    if (
        attempted
        and not ok
        and not failed_files
        and error_category is None
    ):
        errors.append(
            "failed processing requires file-level or aggregate "
            "failure evidence"
        )
    return ProcessingEvidence(
        attempted=attempted,
        ok=ok,
        failed_files=failed_files,
        warnings=warnings,
        error_category=error_category,
        error_message=error_message,
    )


def _normalize_file(
    value: Any,
    *,
    index: int,
    errors: list[str],
) -> FilePersistenceEvidence:
    prefix = f"persistence.files[{index}]"
    fields = (
        "file_path",
        "action",
        "processing_status",
        "embedding_status",
        "persistence_status",
        "embedding_required",
        "error_category",
        "error_message",
    )
    values = _record_values(
        value,
        record_type=FilePersistenceEvidence,
        fields=fields,
        errors=errors,
        field_name=prefix,
    )
    file_path = _normalize_path(
        values.get("file_path"),
        field_name=f"{prefix}.file_path",
        errors=errors,
    )
    action = values.get("action")
    if type(action) is not str or action not in FILE_ACTIONS:
        errors.append(f"{prefix}.action is not a stable file action")
        action = FILE_ACTION_NOT_REQUIRED
    processing_status = values.get("processing_status")
    if (
        type(processing_status) is not str
        or processing_status not in PROCESSING_STATUSES
    ):
        errors.append(
            f"{prefix}.processing_status is not a stable status"
        )
        processing_status = PROCESSING_STATUS_BLOCKED
    embedding_status = values.get("embedding_status")
    if (
        type(embedding_status) is not str
        or embedding_status not in EMBEDDING_STATUSES
    ):
        errors.append(
            f"{prefix}.embedding_status is not a stable status"
        )
        embedding_status = EMBEDDING_STATUS_BLOCKED
    persistence_status = values.get("persistence_status")
    if (
        type(persistence_status) is not str
        or persistence_status not in FILE_PERSISTENCE_STATUSES
    ):
        errors.append(
            f"{prefix}.persistence_status is not a stable status"
        )
        persistence_status = FILE_PERSISTENCE_BLOCKED
    embedding_required = _strict_bool(
        values.get("embedding_required", False),
        field_name=f"{prefix}.embedding_required",
        errors=errors,
    )
    error_category = _safe_text(
        values.get("error_category"),
        field_name=f"{prefix}.error_category",
        errors=errors,
    )
    error_message = _safe_text(
        values.get("error_message"),
        field_name=f"{prefix}.error_message",
        errors=errors,
        maximum=MAX_ERROR_MESSAGE_LENGTH,
        require_pre_redacted=True,
    )

    successful_statuses = {
        FILE_PERSISTENCE_NOT_REQUIRED,
        FILE_PERSISTENCE_PERSISTED,
        FILE_PERSISTENCE_DELETED,
        FILE_PERSISTENCE_SKIPPED_UNCHANGED,
    }
    if persistence_status in successful_statuses and (
        error_category is not None or error_message is not None
    ):
        errors.append(
            f"{prefix} successful outcome cannot contain an error"
        )
    if persistence_status in FILE_FAILURE_STATUSES and (
        error_category is None
    ):
        errors.append(
            f"{prefix} failed outcome requires error_category"
        )
    if persistence_status == FILE_PERSISTENCE_PERSISTED and (
        action not in {
            FILE_ACTION_ADDED,
            FILE_ACTION_MODIFIED,
            FILE_ACTION_FULL_REFRESH,
        }
        or processing_status != PROCESSING_STATUS_PROCESSED
        or embedding_status
        not in {
            EMBEDDING_STATUS_EMBEDDED,
            EMBEDDING_STATUS_NOT_REQUIRED,
        }
        or (
            embedding_required
            and embedding_status != EMBEDDING_STATUS_EMBEDDED
        )
    ):
        errors.append(
            f"{prefix} persisted outcome contradicts its action or "
            "processing/embedding evidence"
        )
    if persistence_status == FILE_PERSISTENCE_DELETED and (
        action != FILE_ACTION_DELETED
        or processing_status != PROCESSING_STATUS_NOT_REQUIRED
        or embedding_status != EMBEDDING_STATUS_NOT_REQUIRED
        or embedding_required
    ):
        errors.append(
            f"{prefix} deleted outcome requires action=deleted"
        )
    if (
        persistence_status == FILE_PERSISTENCE_SKIPPED_UNCHANGED
        and (
            action != FILE_ACTION_UNCHANGED
            or processing_status != PROCESSING_STATUS_NOT_REQUIRED
            or embedding_status != EMBEDDING_STATUS_NOT_REQUIRED
            or embedding_required
        )
    ):
        errors.append(
            f"{prefix} skipped_unchanged requires action=unchanged"
        )
    if persistence_status == FILE_PERSISTENCE_NOT_REQUIRED and (
        action != FILE_ACTION_NOT_REQUIRED
        or processing_status != PROCESSING_STATUS_NOT_REQUIRED
        or embedding_status != EMBEDDING_STATUS_NOT_REQUIRED
        or embedding_required
    ):
        errors.append(
            f"{prefix} not_required requires action=not_required"
        )
    if (
        action
        in {
            FILE_ACTION_ADDED,
            FILE_ACTION_MODIFIED,
            FILE_ACTION_FULL_REFRESH,
        }
        and persistence_status
        not in {
            FILE_PERSISTENCE_PERSISTED,
            FILE_PERSISTENCE_PENDING,
            FILE_PERSISTENCE_PARSE_FAILED,
            FILE_PERSISTENCE_EMBEDDING_FAILED,
            FILE_PERSISTENCE_REPLACEMENT_FAILED,
            FILE_PERSISTENCE_BLOCKED,
        }
    ):
        errors.append(
            f"{prefix} added/modified/full_refresh file has an "
            "incompatible persistence outcome"
        )
    if action == FILE_ACTION_DELETED and persistence_status not in {
        FILE_PERSISTENCE_DELETED,
        FILE_PERSISTENCE_PENDING,
        FILE_PERSISTENCE_DELETION_FAILED,
        FILE_PERSISTENCE_BLOCKED,
    }:
        errors.append(
            f"{prefix} deleted file has an incompatible outcome"
        )
    if action == FILE_ACTION_UNCHANGED and persistence_status not in {
        FILE_PERSISTENCE_SKIPPED_UNCHANGED,
        FILE_PERSISTENCE_PENDING,
        FILE_PERSISTENCE_BLOCKED,
    }:
        errors.append(
            f"{prefix} unchanged file has an incompatible outcome"
        )
    if (
        persistence_status == FILE_PERSISTENCE_PARSE_FAILED
        and processing_status != PROCESSING_STATUS_PARSE_FAILED
    ):
        errors.append(
            f"{prefix} parse_failed outcome requires parse_failed "
            "processing evidence"
        )
    if (
        persistence_status == FILE_PERSISTENCE_EMBEDDING_FAILED
        and (
            processing_status != PROCESSING_STATUS_PROCESSED
            or embedding_status != EMBEDDING_STATUS_FAILED
            or not embedding_required
        )
    ):
        errors.append(
            f"{prefix} embedding_failed outcome requires failed "
            "embedding evidence"
        )
    if (
        persistence_status == FILE_PERSISTENCE_REPLACEMENT_FAILED
        and (
            processing_status != PROCESSING_STATUS_PROCESSED
            or embedding_status
            not in {
                EMBEDDING_STATUS_EMBEDDED,
                EMBEDDING_STATUS_NOT_REQUIRED,
            }
            or (
                embedding_required
                and embedding_status != EMBEDDING_STATUS_EMBEDDED
            )
        )
    ):
        errors.append(
            f"{prefix} replacement_failed outcome contradicts "
            "processing/embedding evidence"
        )
    if (
        persistence_status == FILE_PERSISTENCE_DELETION_FAILED
        and (
            action != FILE_ACTION_DELETED
            or processing_status != PROCESSING_STATUS_NOT_REQUIRED
            or embedding_status != EMBEDDING_STATUS_NOT_REQUIRED
            or embedding_required
        )
    ):
        errors.append(
            f"{prefix} deletion_failed outcome contradicts "
            "processing/embedding evidence"
        )
    return FilePersistenceEvidence(
        file_path=file_path,
        action=action,
        processing_status=processing_status,
        embedding_status=embedding_status,
        persistence_status=persistence_status,
        embedding_required=embedding_required,
        error_category=error_category,
        error_message=error_message,
    )


def _normalize_persistence(
    value: Any,
    errors: list[str],
) -> PersistenceEvidence:
    fields = (
        "required",
        "enabled",
        "attempted",
        "ok",
        "index_scope",
        "files",
        "required_files",
        "aborted_after_failure",
        "unattempted_required_files",
        "failure_stage",
        "error_category",
        "error_message",
    )
    values = _record_values(
        value,
        record_type=PersistenceEvidence,
        fields=fields,
        errors=errors,
        field_name="persistence",
    )
    required = _strict_bool(
        values.get("required"),
        field_name="persistence.required",
        errors=errors,
    )
    enabled = _strict_bool(
        values.get("enabled"),
        field_name="persistence.enabled",
        errors=errors,
    )
    attempted = _strict_bool(
        values.get("attempted"),
        field_name="persistence.attempted",
        errors=errors,
    )
    ok = _strict_bool(
        values.get("ok"),
        field_name="persistence.ok",
        errors=errors,
    )
    index_scope = _safe_text(
        values.get("index_scope"),
        field_name="persistence.index_scope",
        errors=errors,
        maximum=512,
        require_pre_redacted=True,
    )
    aborted = _strict_bool(
        values.get("aborted_after_failure", False),
        field_name="persistence.aborted_after_failure",
        errors=errors,
    )
    raw_files = _sequence(
        values.get("files", ()),
        field_name="persistence.files",
        errors=errors,
    )
    normalized_files = tuple(
        _normalize_file(item, index=index, errors=errors)
        for index, item in enumerate(raw_files)
    )
    paths = [item.file_path for item in normalized_files if item.file_path]
    if len(
        {_path_comparison_key(item) for item in paths}
    ) != len(paths):
        errors.append(
            "persistence.files contains duplicate or conflicting file "
            "records"
        )
    files = tuple(
        sorted(normalized_files, key=lambda item: item.file_path)
    )
    unattempted = _normalize_paths(
        values.get("unattempted_required_files", ()),
        field_name="persistence.unattempted_required_files",
        errors=errors,
    )
    required_files = _normalize_paths(
        values.get("required_files", ()),
        field_name="persistence.required_files",
        errors=errors,
    )
    failure_stage = _safe_text(
        values.get("failure_stage"),
        field_name="persistence.failure_stage",
        errors=errors,
    )
    error_category = _safe_text(
        values.get("error_category"),
        field_name="persistence.error_category",
        errors=errors,
    )
    error_message = _safe_text(
        values.get("error_message"),
        field_name="persistence.error_message",
        errors=errors,
        maximum=MAX_ERROR_MESSAGE_LENGTH,
        require_pre_redacted=True,
    )

    by_path = {item.file_path: item for item in files}
    evidenced_required_files = {
        item.file_path
        for item in files
        if item.action != FILE_ACTION_NOT_REQUIRED
    }
    if set(required_files) != evidenced_required_files:
        errors.append(
            "required_files must exactly match all required file "
            "outcome records"
        )
    expected_unattempted = {
        item.file_path
        for item in files
        if item.persistence_status
        in {
            FILE_PERSISTENCE_PENDING,
            FILE_PERSISTENCE_BLOCKED,
        }
        and item.action != FILE_ACTION_NOT_REQUIRED
        and enabled
    }
    if set(unattempted) != expected_unattempted:
        errors.append(
            "unattempted_required_files must exactly identify required "
            "pending/blocked file outcomes"
        )
    if any(path not in by_path for path in unattempted):
        errors.append(
            "unattempted_required_files contains a file without evidence"
        )
    failed = [
        item
        for item in files
        if item.persistence_status in FILE_FAILURE_STATUSES
    ]
    if ok and not attempted:
        errors.append("persistence ok=true requires attempted=true")
    if ok and not enabled:
        errors.append("persistence ok=true while persistence is disabled")
    if not enabled and attempted:
        errors.append(
            "disabled persistence cannot report attempted persistent work"
        )
    if not enabled and aborted:
        errors.append(
            "intentionally disabled persistence cannot report a "
            "mid-run abort"
        )
    if not enabled and any(
        item.persistence_status
        not in {
            FILE_PERSISTENCE_BLOCKED,
            FILE_PERSISTENCE_NOT_REQUIRED,
        }
        for item in files
    ):
        errors.append(
            "disabled persistence can only report blocked/not_required "
            "file outcomes"
        )
    if ok and (failed or unattempted or aborted):
        errors.append(
            "persistence ok=true contradicts failed, aborted, or "
            "unattempted required file evidence"
        )
    if aborted and not failed and error_category is None:
        errors.append(
            "persistence_aborted_after_failure requires file-level or "
            "global persistence failure evidence"
        )
    if aborted and not unattempted:
        errors.append(
            "persistence_aborted_after_failure requires remaining "
            "unattempted required files"
        )
    if unattempted and not aborted:
        errors.append(
            "unattempted required files require "
            "persistence_aborted_after_failure=true"
        )
    if required and ok:
        for item in files:
            expected = {
                FILE_ACTION_ADDED: FILE_PERSISTENCE_PERSISTED,
                FILE_ACTION_MODIFIED: FILE_PERSISTENCE_PERSISTED,
                FILE_ACTION_FULL_REFRESH: FILE_PERSISTENCE_PERSISTED,
                FILE_ACTION_DELETED: FILE_PERSISTENCE_DELETED,
                FILE_ACTION_UNCHANGED: (
                    FILE_PERSISTENCE_SKIPPED_UNCHANGED
                ),
                FILE_ACTION_NOT_REQUIRED: FILE_PERSISTENCE_NOT_REQUIRED,
            }[item.action]
            if item.persistence_status != expected:
                errors.append(
                    "persistence ok=true contradicts file outcome for "
                    f"{item.file_path}"
                )
    if not required and ok:
        errors.append(
            "canonical persistence success requires required=true"
        )
    if ok and not required_files:
        errors.append(
            "persistent success requires a non-empty required_files "
            "evidence set"
        )
    if ok and index_scope is None:
        errors.append(
            "persistent success requires its exact index_scope"
        )
    if ok and (
        error_category is not None or error_message is not None
    ):
        errors.append(
            "successful persistence cannot contain aggregate errors"
        )
    if ok and failure_stage is not None:
        errors.append(
            "successful persistence cannot contain failure_stage"
        )
    if (
        required
        and enabled
        and attempted
        and not ok
        and not failed
        and not unattempted
        and error_category is None
    ):
        errors.append(
            "failed persistence requires file-level or aggregate "
            "failure evidence"
        )
    return PersistenceEvidence(
        required=required,
        enabled=enabled,
        attempted=attempted,
        ok=ok,
        index_scope=index_scope,
        files=files,
        required_files=required_files,
        aborted_after_failure=aborted,
        unattempted_required_files=unattempted,
        failure_stage=failure_stage,
        error_category=error_category,
        error_message=error_message,
    )


def _normalize_reconciliation(
    value: Any,
    errors: list[str],
) -> ReconciliationEvidence:
    fields = (
        "required",
        "attempted",
        "ok",
        "index_scope",
        "deleted_units",
        "deleted_dependencies",
        "preserved_external_targets",
        "skipped_reason",
        "error_category",
        "error_message",
    )
    values = _record_values(
        value,
        record_type=ReconciliationEvidence,
        fields=fields,
        errors=errors,
        field_name="reconciliation",
    )
    required = _strict_bool(
        values.get("required"),
        field_name="reconciliation.required",
        errors=errors,
    )
    attempted = _strict_bool(
        values.get("attempted"),
        field_name="reconciliation.attempted",
        errors=errors,
    )
    ok = _strict_bool(
        values.get("ok"),
        field_name="reconciliation.ok",
        errors=errors,
    )
    index_scope = _safe_text(
        values.get("index_scope"),
        field_name="reconciliation.index_scope",
        errors=errors,
        maximum=512,
        require_pre_redacted=True,
    )
    deleted_units = _nonnegative_int(
        values.get("deleted_units", 0),
        field_name="reconciliation.deleted_units",
        errors=errors,
    )
    deleted_dependencies = _nonnegative_int(
        values.get("deleted_dependencies", 0),
        field_name="reconciliation.deleted_dependencies",
        errors=errors,
    )
    preserved = _nonnegative_int(
        values.get("preserved_external_targets", 0),
        field_name="reconciliation.preserved_external_targets",
        errors=errors,
    )
    skipped_reason = _safe_text(
        values.get("skipped_reason"),
        field_name="reconciliation.skipped_reason",
        errors=errors,
        maximum=MAX_ERROR_MESSAGE_LENGTH,
        require_pre_redacted=True,
    )
    error_category = _safe_text(
        values.get("error_category"),
        field_name="reconciliation.error_category",
        errors=errors,
    )
    error_message = _safe_text(
        values.get("error_message"),
        field_name="reconciliation.error_message",
        errors=errors,
        maximum=MAX_ERROR_MESSAGE_LENGTH,
        require_pre_redacted=True,
    )
    if ok and not attempted:
        errors.append("reconciliation ok=true requires attempted=true")
    if attempted and index_scope is None:
        errors.append(
            "attempted reconciliation requires its exact index_scope"
        )
    if ok and (
        skipped_reason is not None
        or error_category is not None
        or error_message is not None
    ):
        errors.append(
            "successful reconciliation cannot contain skip/error evidence"
        )
    if attempted and not ok and error_category is None:
        errors.append(
            "failed reconciliation requires error_category"
        )
    if not attempted and any(
        (deleted_units, deleted_dependencies, preserved)
    ):
        errors.append(
            "unattempted reconciliation cannot report row counts"
        )
    if required and not attempted and skipped_reason is None:
        errors.append(
            "required unattempted reconciliation must record skipped_reason"
        )
    return ReconciliationEvidence(
        required=required,
        attempted=attempted,
        ok=ok,
        index_scope=index_scope,
        deleted_units=deleted_units,
        deleted_dependencies=deleted_dependencies,
        preserved_external_targets=preserved,
        skipped_reason=skipped_reason,
        error_category=error_category,
        error_message=error_message,
    )


def _normalize_auxiliary(
    value: Any,
    errors: list[str],
) -> tuple[AuxiliaryEvidence, ...]:
    if value is None:
        return ()
    raw_items = (
        (value,)
        if isinstance(value, (AuxiliaryEvidence, Mapping))
        else _sequence(
            value,
            field_name="auxiliary",
            errors=errors,
        )
    )
    normalized: list[AuxiliaryEvidence] = []
    seen: set[str] = set()
    fields = (
        "component",
        "authority",
        "attempted",
        "ok",
        "error_category",
        "error_message",
    )
    for index, item in enumerate(raw_items):
        prefix = f"auxiliary[{index}]"
        values = _record_values(
            item,
            record_type=AuxiliaryEvidence,
            fields=fields,
            errors=errors,
            field_name=prefix,
        )
        component = _safe_text(
            values.get("component"),
            field_name=f"{prefix}.component",
            errors=errors,
            allow_none=False,
        ) or ""
        authority = values.get("authority")
        if (
            type(authority) is not str
            or authority not in AUXILIARY_AUTHORITIES
        ):
            errors.append(
                f"{prefix}.authority is not a stable authority class"
            )
            authority = AUXILIARY_AUTHORITY_UNKNOWN
        attempted = _strict_bool(
            values.get("attempted"),
            field_name=f"{prefix}.attempted",
            errors=errors,
        )
        ok = _strict_bool(
            values.get("ok"),
            field_name=f"{prefix}.ok",
            errors=errors,
        )
        error_category = _safe_text(
            values.get("error_category"),
            field_name=f"{prefix}.error_category",
            errors=errors,
        )
        error_message = _safe_text(
            values.get("error_message"),
            field_name=f"{prefix}.error_message",
            errors=errors,
            maximum=MAX_ERROR_MESSAGE_LENGTH,
            require_pre_redacted=True,
        )
        if component in seen:
            errors.append(
                "auxiliary contains duplicate component evidence"
            )
        seen.add(component)
        if ok and not attempted:
            errors.append(f"{prefix} ok=true requires attempted=true")
        if ok and (
            error_category is not None or error_message is not None
        ):
            errors.append(
                f"{prefix} successful outcome cannot contain an error"
            )
        if not ok and attempted and error_category is None:
            errors.append(
                f"{prefix} failed outcome requires error_category"
            )
        if authority == AUXILIARY_AUTHORITY_UNKNOWN:
            errors.append(
                f"{prefix} has unknown completion authority"
            )
        normalized.append(
            AuxiliaryEvidence(
                component=component,
                authority=authority,
                attempted=attempted,
                ok=ok,
                error_category=error_category,
                error_message=error_message,
            )
        )
    return tuple(sorted(normalized, key=lambda item: item.component))


def _normalize_run_id(
    value: Any,
    *,
    errors: list[str],
) -> str | None:
    if value is None:
        return None
    return _safe_text(
        value,
        field_name="completion_run_id",
        errors=errors,
        allow_none=False,
        maximum=256,
    )


def _file_failure_stage(
    files: tuple[FilePersistenceEvidence, ...],
) -> str | None:
    priority = (
        (FILE_PERSISTENCE_PARSE_FAILED, "processing"),
        (FILE_PERSISTENCE_EMBEDDING_FAILED, "embedding"),
        (FILE_PERSISTENCE_REPLACEMENT_FAILED, "replacement"),
        (FILE_PERSISTENCE_DELETION_FAILED, "deletion"),
        (FILE_PERSISTENCE_BLOCKED, "persistence"),
    )
    statuses = {item.persistence_status for item in files}
    for status, stage in priority:
        if status in statuses:
            return stage
    return None


def classify_index_completion(
    *,
    identity_state: RepositoryIdentityState | None,
    processing: ProcessingEvidence | Mapping[str, Any],
    persistence: PersistenceEvidence | Mapping[str, Any],
    reconciliation: ReconciliationEvidence | Mapping[str, Any],
    auxiliary: (
        AuxiliaryEvidence
        | Mapping[str, Any]
        | Sequence[AuxiliaryEvidence | Mapping[str, Any]]
        | None
    ) = None,
    completion_run_id: str | None = None,
    observed_state_id: str | None = None,
) -> IndexCompletionDecision:
    """Classify supplied evidence without performing or trusting any work.

    ``trusted_completion`` is derived here and is intentionally not an input.
    Contradictory, malformed, duplicate, conflicting, unsafe, or
    credential-bearing evidence produces ``invalid_completion_evidence`` and
    all trust/advancement fields fail closed.
    """
    errors: list[str] = []
    identity = _normalize_identity(identity_state, errors)
    processing_record = _normalize_processing(processing, errors)
    persistence_record = _normalize_persistence(
        persistence,
        errors,
    )
    reconciliation_record = _normalize_reconciliation(
        reconciliation,
        errors,
    )
    auxiliary_records = _normalize_auxiliary(auxiliary, errors)
    run_id = _normalize_run_id(completion_run_id, errors=errors)
    observed_id = (
        None
        if observed_state_id is None
        else _safe_text(
            observed_state_id,
            field_name="observed_state_id",
            errors=errors,
            allow_none=False,
            maximum=256,
            require_pre_redacted=True,
        )
    )

    file_failed = {
        item.file_path
        for item in persistence_record.files
        if item.persistence_status in FILE_FAILURE_STATUSES
    }
    failed_files = tuple(
        sorted(
            set(processing_record.failed_files)
            | file_failed
        )
    )
    processing_failed_evidence = {
        item.file_path
        for item in persistence_record.files
        if item.processing_status
        in {
            PROCESSING_STATUS_PARSE_FAILED,
            PROCESSING_STATUS_PENDING,
            PROCESSING_STATUS_BLOCKED,
        }
    }
    if processing_record.ok and processing_failed_evidence:
        errors.append(
            "processing ok=true contradicts failed/pending/blocked "
            "file processing evidence"
        )
    if set(processing_record.failed_files) != processing_failed_evidence:
        errors.append(
            "processing failed_files must exactly match failed/pending/"
            "blocked file processing evidence"
        )
    if persistence_record.ok and failed_files:
        errors.append(
            "persistence ok=true contradicts non-empty failed_files"
        )
    if (
        persistence_record.ok
        and processing_record.failed_files
    ):
        errors.append(
            "persistent success cannot coexist with processing failures"
        )
    if (
        not persistence_record.ok
        and reconciliation_record.attempted
    ):
        errors.append(
            "reconciliation must not be attempted after required "
            "persistence failure"
        )
    if (
        persistence_record.ok
        and identity.active_index_scope is not None
        and persistence_record.index_scope
        != identity.active_index_scope
    ):
        errors.append(
            "persistence index_scope does not match confirmed "
            "repository/epoch identity"
        )
    if (
        reconciliation_record.attempted
        and reconciliation_record.index_scope
        != persistence_record.index_scope
    ):
        errors.append(
            "reconciliation index_scope does not match persistence "
            "index_scope"
        )
    if (
        reconciliation_record.attempted
        and identity.active_index_scope is not None
        and reconciliation_record.index_scope
        != identity.active_index_scope
    ):
        errors.append(
            "reconciliation index_scope does not match repository/"
            "epoch identity"
        )
    file_failure_stages = {
        stage
        for item in persistence_record.files
        for status, stage in (
            (
                FILE_PERSISTENCE_PARSE_FAILED,
                "processing",
            ),
            (
                FILE_PERSISTENCE_EMBEDDING_FAILED,
                "embedding",
            ),
            (
                FILE_PERSISTENCE_REPLACEMENT_FAILED,
                "replacement",
            ),
            (
                FILE_PERSISTENCE_DELETION_FAILED,
                "deletion",
            ),
            (
                FILE_PERSISTENCE_BLOCKED,
                "persistence",
            ),
        )
        if item.persistence_status == status
    }
    stable_failure_stages = {
        "processing",
        "initialization",
        "embedding",
        "replacement",
        "deletion",
        "persistence",
    }
    aggregate_failure_stages = set()
    if (
        not persistence_record.ok
        and persistence_record.error_category
        == "database_initialization_failed"
    ):
        aggregate_failure_stages.add("initialization")
    if (
        persistence_record.failure_stage is not None
        and persistence_record.failure_stage not in stable_failure_stages
    ):
        errors.append("persistence.failure_stage is not stable")
    if (
        file_failure_stages
        and persistence_record.failure_stage is not None
        and persistence_record.failure_stage
        not in file_failure_stages | aggregate_failure_stages
    ):
        errors.append(
            "persistence.failure_stage contradicts file outcomes"
        )

    authoritative_failures = tuple(
        item.component
        for item in auxiliary_records
        if (
            item.authority == AUXILIARY_AUTHORITY_AUTHORITATIVE
            and (not item.attempted or not item.ok)
        )
    )
    warning_only_failures = tuple(
        item.component
        for item in auxiliary_records
        if (
            item.authority == AUXILIARY_AUTHORITY_OUTPUT
            and (not item.attempted or not item.ok)
        )
    )
    graph_records = tuple(
        item
        for item in auxiliary_records
        if "graph" in item.component.casefold()
    )
    auxiliary_graph_ok = (
        None
        if not graph_records
        else all(item.attempted and item.ok for item in graph_records)
    )

    warnings = set(processing_record.warnings)
    warnings.update(
        f"auxiliary_output_failed: {component}"
        for component in warning_only_failures
    )
    reasons: list[str] = []
    failure_stage: str | None = None

    if errors:
        status = STATUS_INVALID_COMPLETION_EVIDENCE
        reasons.extend(sorted(set(errors)))
        failure_stage = "evidence"
    elif not processing_record.attempted or not processing_record.ok:
        status = STATUS_PROCESSING_FAILED
        reasons.append(
            "required source processing did not complete successfully"
        )
        failure_stage = (
            _file_failure_stage(persistence_record.files)
            or "processing"
        )
    elif not persistence_record.enabled:
        status = STATUS_PERSISTENCE_DISABLED
        reasons.append(
            "database persistence is disabled and cannot count as "
            "persistent success"
        )
        failure_stage = "persistence"
    elif (
        not persistence_record.required
        or not persistence_record.attempted
    ):
        status = STATUS_PERSISTENCE_NOT_ATTEMPTED
        reasons.append(
            "canonical persistence was required by the completion "
            "contract but was not attempted"
        )
        failure_stage = "persistence"
    elif not persistence_record.ok:
        status = STATUS_PERSISTENCE_FAILED
        reasons.append(
            "one or more required persistent operations failed or "
            "remained unattempted"
        )
        failure_stage = (
            persistence_record.failure_stage
            or _file_failure_stage(persistence_record.files)
            or "persistence"
        )
    elif (
        (
            reconciliation_record.required
            and (
                not reconciliation_record.attempted
                or not reconciliation_record.ok
            )
        )
        or (
            reconciliation_record.attempted
            and not reconciliation_record.ok
        )
    ):
        status = STATUS_RECONCILIATION_FAILED
        reasons.append(
            "required scope reconciliation did not complete "
            "successfully"
        )
        failure_stage = "reconciliation"
    elif (
        identity.identity_status != IDENTITY_STATUS_CONFIRMED
        or not identity.canonical_mutation_allowed
        or (
            reconciliation_record.required
            and not identity.reconciliation_allowed
        )
        or not identity.applied_manifest_advance_allowed
    ):
        status = STATUS_IDENTITY_BLOCKED
        reasons.append(
            "identity confirmation or architecture-epoch permissions "
            "do not authorize canonical mutation"
        )
        failure_stage = "identity"
    elif authoritative_failures:
        status = STATUS_AUXILIARY_FAILED
        reasons.append(
            "an authoritative completion dependency failed: "
            + ", ".join(authoritative_failures)
        )
        failure_stage = "auxiliary"
    elif warning_only_failures or warnings:
        status = STATUS_COMPLETE_WITH_WARNINGS
        reasons.append(
            "canonical persistence and reconciliation completed; only "
            "explicitly non-authoritative outputs warned or failed"
        )
    else:
        status = STATUS_COMPLETE
        reasons.append(
            "all required processing, persistence, and reconciliation "
            "completed under confirmed identity"
        )

    evidence_validated = not errors
    trusted = status in {
        STATUS_COMPLETE,
        STATUS_COMPLETE_WITH_WARNINGS,
    }
    manifest_allowed = (
        trusted
        and evidence_validated
        and identity.identity_status == IDENTITY_STATUS_CONFIRMED
        and identity.applied_manifest_advance_allowed
        and persistence_record.required
        and persistence_record.attempted
        and persistence_record.ok
        and (
            not reconciliation_record.required
            or (
                reconciliation_record.attempted
                and reconciliation_record.ok
            )
        )
    )
    if not evidence_validated:
        failed_files = tuple(sorted(set(failed_files)))

    return IndexCompletionDecision(
        processing_ok=(
            evidence_validated
            and processing_record.attempted
            and processing_record.ok
        ),
        persistence_required=persistence_record.required,
        persistence_attempted=persistence_record.attempted,
        persistence_ok=(
            evidence_validated and persistence_record.ok
        ),
        reconciliation_required=reconciliation_record.required,
        reconciliation_attempted=reconciliation_record.attempted,
        reconciliation_ok=(
            evidence_validated and reconciliation_record.ok
        ),
        auxiliary_graph_ok=auxiliary_graph_ok,
        trusted_completion=trusted,
        manifest_advance_allowed=manifest_allowed,
        trusted_current_claim_allowed=False,
        current_claim_requires_manifest_commit=True,
        status=status,
        failure_stage=failure_stage,
        failed_files=failed_files,
        warnings=tuple(sorted(warnings)),
        reasons=tuple(reasons),
        identity_status=identity.identity_status,
        repository_id=identity.repository_id,
        active_index_scope=identity.active_index_scope,
        architecture_epoch=identity.architecture_epoch,
        identity_state_revision=identity.state_revision,
        completion_run_id=run_id,
        observed_state_id=observed_id,
        persistence_aborted_after_failure=(
            persistence_record.aborted_after_failure
        ),
        unattempted_required_files=(
            persistence_record.unattempted_required_files
        ),
        reconciliation_skipped_reason=(
            reconciliation_record.skipped_reason
        ),
        file_outcomes=persistence_record.files,
        auxiliary_outcomes=auxiliary_records,
        evidence_validated=evidence_validated,
        _identity_source=(
            identity_state
            if isinstance(identity_state, RepositoryIdentityState)
            else None
        ),
        _processing_source=processing_record,
        _persistence_source=persistence_record,
        _reconciliation_source=reconciliation_record,
        _auxiliary_source=auxiliary_records,
        _completion_run_id_source=run_id,
        _observed_state_id_source=observed_id,
        _classifier_token=_CLASSIFIER_TOKEN,
    )


def _completion_provenance_errors(
    decision: Any,
) -> tuple[str, ...]:
    if not isinstance(decision, IndexCompletionDecision):
        return (
            "completion_decision was not produced by the classifier",
        )
    if decision._classifier_token is not _CLASSIFIER_TOKEN:
        return (
            "completion_decision lacks classifier provenance",
        )
    if decision.contract_version != COMPLETION_CONTRACT_VERSION:
        return ("completion contract version is not supported",)
    try:
        reclassified = classify_index_completion(
            identity_state=decision._identity_source,
            processing=decision._processing_source,
            persistence=decision._persistence_source,
            reconciliation=decision._reconciliation_source,
            auxiliary=decision._auxiliary_source,
            completion_run_id=decision._completion_run_id_source,
            observed_state_id=decision._observed_state_id_source,
        )
        matches_reclassified = _type_strict_data_equal(
            reclassified.to_dict(),
            decision.to_dict(),
        )
    except Exception:
        return (
            "stored or public completion evidence could not be "
            "reclassified safely",
        )
    if not matches_reclassified:
        return (
            "completion_decision fields do not match reclassified "
            "source evidence",
        )
    return ()


def _completion_integrity_errors(
    decision: Any,
) -> tuple[str, ...]:
    provenance_errors = _completion_provenance_errors(decision)
    if provenance_errors:
        return provenance_errors
    assert isinstance(decision, IndexCompletionDecision)
    errors: list[str] = []
    if not decision.evidence_validated:
        errors.append("completion evidence is invalid")
    if decision.status not in {
        STATUS_COMPLETE,
        STATUS_COMPLETE_WITH_WARNINGS,
    }:
        errors.append(
            f"completion status {decision.status!r} is not trusted"
        )
    if not decision.trusted_completion:
        errors.append("trusted_completion is false")
    if not (
        decision.processing_ok
        and decision.persistence_required
        and decision.persistence_attempted
        and decision.persistence_ok
    ):
        errors.append(
            "processing or required persistence is incomplete"
        )
    if decision.reconciliation_required and not (
        decision.reconciliation_attempted
        and decision.reconciliation_ok
    ):
        errors.append("required reconciliation is incomplete")
    if (
        decision.failed_files
        or decision.unattempted_required_files
        or decision.persistence_aborted_after_failure
    ):
        errors.append(
            "completion contains failed, unattempted, or aborted work"
        )
    if not decision.manifest_advance_allowed:
        errors.append("completion manifest-advance eligibility is false")
    return tuple(errors)


def _validated_full_identity(
    identity_state: Any,
) -> tuple[bool, tuple[str, ...]]:
    if not isinstance(identity_state, RepositoryIdentityState):
        return (
            False,
            (
                "a full RepositoryIdentityState is required; compact "
                "permissions are insufficient",
            ),
        )
    validation = validate_repository_identity_state(identity_state)
    permissions = derive_canonical_identity_permissions(identity_state)
    errors: list[str] = []
    if not validation.valid:
        _extend_safe_validation_reasons(
            errors,
            validation.errors or ("identity state is invalid",),
            prefix="identity_state",
        )
    if identity_state.identity_status != IDENTITY_STATUS_CONFIRMED:
        errors.append("identity status is not confirmed")
    if not (
        permissions.canonical_build_allowed
        or permissions.canonical_refresh_allowed
    ):
        errors.append("canonical mutation permission is false")
    if not permissions.reconciliation_allowed:
        errors.append("reconciliation permission is false")
    if not permissions.applied_manifest_advance_allowed:
        errors.append("identity manifest-advance permission is false")
    return (not errors, tuple(errors))


def may_advance_applied_manifest(
    *,
    identity_state: RepositoryIdentityState,
    completion_decision: IndexCompletionDecision,
) -> ManifestAdvanceDecision:
    """Require independently valid identity and classified completion."""
    identity_ok, identity_errors = _validated_full_identity(
        identity_state
    )
    provenance_errors = _completion_provenance_errors(
        completion_decision
    )
    completion_errors = _completion_integrity_errors(
        completion_decision
    )
    if provenance_errors or (
        isinstance(completion_decision, IndexCompletionDecision)
        and not completion_decision.evidence_validated
    ):
        invalid_reasons = (
            provenance_errors
            or ("completion evidence is invalid",)
        )
        return ManifestAdvanceDecision(
            allowed=False,
            status=MANIFEST_GATE_INVALID,
            reason=invalid_reasons[0],
            reasons=invalid_reasons,
        )
    if not identity_ok:
        return ManifestAdvanceDecision(
            allowed=False,
            status=MANIFEST_GATE_IDENTITY_BLOCKED,
            reason=identity_errors[0],
            reasons=identity_errors,
        )
    assert isinstance(completion_decision, IndexCompletionDecision)
    decision_binding = (
        completion_decision.identity_status,
        completion_decision.repository_id,
        completion_decision.active_index_scope,
        completion_decision.architecture_epoch,
        completion_decision.identity_state_revision,
    )
    identity_binding = (
        identity_state.identity_status,
        identity_state.repository_id,
        identity_state.active_index_scope,
        identity_state.architecture_epoch,
        identity_state.state_revision,
    )
    if decision_binding != identity_binding:
        mismatch = (
            "completion repository/epoch/scope identity binding does "
            "not match the supplied identity state",
        )
        return ManifestAdvanceDecision(
            allowed=False,
            status=MANIFEST_GATE_INVALID,
            reason=mismatch[0],
            reasons=mismatch,
        )
    if completion_errors:
        return ManifestAdvanceDecision(
            allowed=False,
            status=MANIFEST_GATE_COMPLETION_BLOCKED,
            reason=completion_errors[0],
            reasons=completion_errors,
        )
    return ManifestAdvanceDecision(
        allowed=True,
        status=MANIFEST_GATE_ALLOWED,
        reason=(
            "confirmed identity and trusted persistence/reconciliation "
            "allow an applied-manifest commit"
        ),
    )


def may_claim_repository_intelligence_current(
    *,
    identity_state: RepositoryIdentityState,
    completion_decision: IndexCompletionDecision,
    applied_manifest: AppliedManifestEvidence,
) -> TrustedCurrentClaimDecision:
    """Require a matching committed applied manifest for a current claim."""
    completion_run_id = (
        completion_decision.completion_run_id
        if isinstance(completion_decision, IndexCompletionDecision)
        else None
    )
    if not isinstance(applied_manifest, AppliedManifestEvidence):
        return TrustedCurrentClaimDecision(
            allowed=False,
            status=CURRENT_CLAIM_INVALID,
            reason=(
                "applied_manifest must be explicit applied-manifest "
                "evidence"
            ),
            completion_run_id=completion_run_id,
            applied_manifest_run_id=None,
            observed_state_id=None,
            applied_state_id=None,
        )

    receipt_errors: list[str] = []

    def receipt_text(value: Any, field_name: str) -> str | None:
        return _safe_text(
            value,
            field_name=field_name,
            errors=receipt_errors,
            allow_none=False,
            maximum=512,
            require_pre_redacted=True,
        )

    receipt_completion_run = receipt_text(
        applied_manifest.completion_run_id,
        "applied_manifest.completion_run_id",
    )
    receipt_applied_run = receipt_text(
        applied_manifest.applied_manifest_run_id,
        "applied_manifest.applied_manifest_run_id",
    )
    receipt_observed_state = receipt_text(
        applied_manifest.observed_state_id,
        "applied_manifest.observed_state_id",
    )
    receipt_applied_state = receipt_text(
        applied_manifest.applied_state_id,
        "applied_manifest.applied_state_id",
    )
    receipt_repository_id = receipt_text(
        applied_manifest.repository_id,
        "applied_manifest.repository_id",
    )
    receipt_index_scope = receipt_text(
        applied_manifest.active_index_scope,
        "applied_manifest.active_index_scope",
    )
    if type(applied_manifest.committed) is not bool:
        receipt_errors.append(
            "applied_manifest.committed must be a boolean"
        )
    if (
        applied_manifest.architecture_epoch is not None
        and (
            type(applied_manifest.architecture_epoch) is not int
            or applied_manifest.architecture_epoch <= 0
        )
    ):
        receipt_errors.append(
            "applied_manifest.architecture_epoch must be a positive "
            "integer or None"
        )
    if (
        type(applied_manifest.identity_state_revision) is not int
        or applied_manifest.identity_state_revision < 0
    ):
        receipt_errors.append(
            "applied_manifest.identity_state_revision must be a "
            "non-negative integer"
        )
    if receipt_errors:
        return TrustedCurrentClaimDecision(
            allowed=False,
            status=CURRENT_CLAIM_INVALID,
            reason="applied-manifest evidence is malformed or unsafe",
            completion_run_id=completion_run_id,
            applied_manifest_run_id=None,
            observed_state_id=None,
            applied_state_id=None,
            reasons=tuple(sorted(set(receipt_errors))),
        )

    gate = may_advance_applied_manifest(
        identity_state=identity_state,
        completion_decision=completion_decision,
    )
    if not gate.allowed:
        status = (
            CURRENT_CLAIM_IDENTITY_BLOCKED
            if gate.status == MANIFEST_GATE_IDENTITY_BLOCKED
            else CURRENT_CLAIM_COMPLETION_BLOCKED
        )
        return TrustedCurrentClaimDecision(
            allowed=False,
            status=status,
            reason=gate.reason,
            completion_run_id=completion_run_id,
            applied_manifest_run_id=receipt_applied_run,
            observed_state_id=receipt_observed_state,
            applied_state_id=receipt_applied_state,
            reasons=gate.reasons,
        )
    if not applied_manifest.committed:
        return TrustedCurrentClaimDecision(
            allowed=False,
            status=CURRENT_CLAIM_MANIFEST_NOT_COMMITTED,
            reason=(
                "completion alone cannot claim current before the "
                "applied manifest commits"
            ),
            completion_run_id=completion_run_id,
            applied_manifest_run_id=receipt_applied_run,
            observed_state_id=receipt_observed_state,
            applied_state_id=receipt_applied_state,
        )
    run_values = (
        completion_run_id,
        receipt_completion_run,
        receipt_applied_run,
    )
    if (
        any(
            not isinstance(value, str) or not value.strip()
            for value in run_values
        )
        or len(set(run_values)) != 1
    ):
        return TrustedCurrentClaimDecision(
            allowed=False,
            status=CURRENT_CLAIM_RUN_MISMATCH,
            reason=(
                "completed run identity does not match applied-manifest "
                "run identity"
            ),
            completion_run_id=completion_run_id,
            applied_manifest_run_id=receipt_applied_run,
            observed_state_id=receipt_observed_state,
            applied_state_id=receipt_applied_state,
        )
    receipt_binding = (
        receipt_repository_id,
        receipt_index_scope,
        applied_manifest.architecture_epoch,
        applied_manifest.identity_state_revision,
    )
    decision_binding = (
        completion_decision.repository_id,
        completion_decision.active_index_scope,
        completion_decision.architecture_epoch,
        completion_decision.identity_state_revision,
    )
    if receipt_binding != decision_binding:
        return TrustedCurrentClaimDecision(
            allowed=False,
            status=CURRENT_CLAIM_RUN_MISMATCH,
            reason=(
                "applied-manifest repository/epoch/scope identity does "
                "not match the completed run"
            ),
            completion_run_id=completion_run_id,
            applied_manifest_run_id=receipt_applied_run,
            observed_state_id=receipt_observed_state,
            applied_state_id=receipt_applied_state,
        )
    state_values = (
        completion_decision.observed_state_id,
        receipt_observed_state,
        receipt_applied_state,
    )
    if (
        any(
            not isinstance(value, str) or not value.strip()
            for value in state_values
        )
        or len(set(state_values)) != 1
    ):
        return TrustedCurrentClaimDecision(
            allowed=False,
            status=CURRENT_CLAIM_STATE_MISMATCH,
            reason=(
                "observed repository state does not match the committed "
                "applied persistent state"
            ),
            completion_run_id=completion_run_id,
            applied_manifest_run_id=receipt_applied_run,
            observed_state_id=receipt_observed_state,
            applied_state_id=receipt_applied_state,
        )
    return TrustedCurrentClaimDecision(
        allowed=True,
        status=CURRENT_CLAIM_ALLOWED,
        reason=(
            "confirmed identity, trusted completion, and matching "
            "applied-manifest run/state evidence permit a current claim"
        ),
        completion_run_id=completion_run_id,
        applied_manifest_run_id=receipt_applied_run,
        observed_state_id=receipt_observed_state,
        applied_state_id=receipt_applied_state,
    )
