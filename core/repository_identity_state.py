"""Persistent human-confirmed identity authority for canonical intelligence.

INDEX.1D.2B answers one narrow question:

    Is this repository identity confirmed strongly enough to permit a
    Canonical Incremental Graph mutation?

The module deliberately does not build or refresh a graph, scan a repository,
access a database or manifest, reconcile rows, call a model, advance completion
state, or run an Activation Graph.  It provides:

* a pure identity-status and permission matrix;
* explicit human decisions and architecture-epoch transitions;
* an advisory classifier over caller-supplied major-change evidence;
* deterministic, strict JSON parsing and serialization; and
* fail-closed, atomic persistence beneath the canonical repository-
  intelligence artifact root.

Initial compatibility
---------------------
The first confirmed architecture retains INDEX.1D.2A's unsuffixed index scope
and is represented by ``architecture_epoch=None``.  A later architecture epoch
must be requested explicitly.  The first requested epoch is ``1`` and every
later request must increment the current integer epoch by exactly one.

Storage namespace
-----------------
The JSON record stores and verifies the full ``repository_id``.  Its directory
uses the bounded 1D.2A ``storage_key`` so an unusually long repository basename
cannot exceed a Windows path-component limit.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
import copy
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
import time
from typing import Any

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from core.repository_identity import (
    RepositoryIdentity,
    build_repository_identity,
    derive_repository_id_from_canonical_root,
    derive_repository_index_scope_from_id,
    derive_repository_storage_key_from_id,
    is_code_index_scope,
    is_repository_id,
)


PHASE_ID = "INDEX.1D.2B"
PHASE_TITLE = "Identity Confirmation & Architecture Epoch State"
SCHEMA_VERSION = 1
ARTIFACT_KIND = "cattus_repository_identity_state"
IDENTITY_STATE_FILENAME = "identity_state.json"
IDENTITY_STATE_LOCK_FILENAME = ".identity_state.lock"
DEFAULT_REPOSITORY_INTELLIGENCE_ROOT = (
    Path(__file__).resolve().parent.parent
    / ".agent"
    / "repository_intelligence"
)
MAX_IDENTITY_STATE_BYTES = 256 * 1024
MAX_REASON_LENGTH = 2_000
MAX_PROJECT_TAG_LENGTH = 128
MAX_ARCHITECTURE_EPOCH = 1_024
MAX_SIGNAL_COUNT = 32
MAX_EVIDENCE_COUNT = 64
MAX_EVIDENCE_LENGTH = 512
MAX_LEGACY_NAMESPACE_COUNT = 64
MAX_LEGACY_NAMESPACE_LENGTH = 256
INTERPROCESS_LOCK_TIMEOUT_SECONDS = 30.0

IDENTITY_STATUS_UNINITIALIZED = "uninitialized"
IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED = (
    "initial_confirmation_required"
)
IDENTITY_STATUS_CONFIRMED = "confirmed"
IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED = (
    "major_change_confirmation_required"
)
IDENTITY_STATUS_ARCHIVED = "archived"
IDENTITY_STATUS_BLOCKED = "blocked"
IDENTITY_STATUSES = (
    IDENTITY_STATUS_UNINITIALIZED,
    IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED,
    IDENTITY_STATUS_CONFIRMED,
    IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED,
    IDENTITY_STATUS_ARCHIVED,
    IDENTITY_STATUS_BLOCKED,
)

DECISION_SAME_PROJECT = "same_project"
DECISION_NEW_ARCHITECTURE_EPOCH = "new_architecture_epoch"
DECISION_NEW_PROJECT = "new_project"
DECISION_REJECT_OR_DEFER = "reject_or_defer"
HUMAN_IDENTITY_DECISIONS = (
    DECISION_SAME_PROJECT,
    DECISION_NEW_ARCHITECTURE_EPOCH,
    DECISION_NEW_PROJECT,
    DECISION_REJECT_OR_DEFER,
)

SIGNAL_ENTRYPOINT_FAMILY_CHANGED = "entrypoint_family_changed"
SIGNAL_PRIMARY_INTERFACE_CHANGED = "primary_interface_changed"
SIGNAL_HIGH_DELETED_FILE_RATIO = "high_deleted_file_ratio"
SIGNAL_HIGH_ADDED_FILE_RATIO = "high_added_file_ratio"
SIGNAL_FRAMEWORK_MANIFEST_CHANGED = "framework_manifest_changed"
SIGNAL_DOMINANT_STRUCTURE_CHANGED = "dominant_structure_changed"
SIGNAL_RUNTIME_ENVIRONMENT_CHANGED = "runtime_environment_changed"
SIGNAL_MANUAL_OPERATOR_FLAG = "manual_operator_flag"
MAJOR_CHANGE_SIGNAL_IDS = (
    SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
    SIGNAL_PRIMARY_INTERFACE_CHANGED,
    SIGNAL_HIGH_DELETED_FILE_RATIO,
    SIGNAL_HIGH_ADDED_FILE_RATIO,
    SIGNAL_FRAMEWORK_MANIFEST_CHANGED,
    SIGNAL_DOMINANT_STRUCTURE_CHANGED,
    SIGNAL_RUNTIME_ENVIRONMENT_CHANGED,
    SIGNAL_MANUAL_OPERATOR_FLAG,
)
_MAJOR_CHANGE_SIGNAL_ALIASES = {
    # INDEX.1D.1 advisory vocabulary.
    "primary_entrypoint_family_change": SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
    "primary_surface_change": SIGNAL_PRIMARY_INTERFACE_CHANGED,
    "high_added_deleted_file_ratio": SIGNAL_HIGH_DELETED_FILE_RATIO,
    "major_framework_or_dependency_manifest_shift": (
        SIGNAL_FRAMEWORK_MANIFEST_CHANGED
    ),
    "dominant_project_structure_change": (
        SIGNAL_DOMINANT_STRUCTURE_CHANGED
    ),
}

ACTIVATION_ALLOWED_IDENTITY_STATUSES = (
    IDENTITY_STATUS_UNINITIALIZED,
    IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED,
    IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED,
    IDENTITY_STATUS_BLOCKED,
)

PERMISSION_LAYER = "identity_only"
TRUSTED_COMPLETION_PHASE = "INDEX.1D.2C"
LEGACY_MIGRATION_PHASE = (
    "INDEX.MIGRATE.1 - Legacy Identity Namespace Inventory"
)
LEGACY_NAMESPACE_WARNING_TEXT = (
    "Legacy inventory-derived namespace evidence is preserved without "
    "deletion, mutation, or automatic epoch binding."
)

_SAFE_STORAGE_SEGMENT_RE = re.compile(r"^[a-z0-9][a-z0-9-]*-[0-9a-f]{16}$")
_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:password|passwd|pwd|token|access_token|refresh_token|"
    r"api_key|apikey|secret|credential)\b\s*[:=]\s*\S+"
)
_CREDENTIAL_URL_RE = re.compile(
    r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@"
)
_SECRET_FIELD_RE = re.compile(
    r"(?i)(?:password|passwd|pwd|token|api[_-]?key|secret|credential)"
)

_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


class IdentityStateError(ValueError):
    """Base error for invalid identity-state input."""


class IdentityStateStorageError(IdentityStateError):
    """Raised internally for an unsafe state-artifact path."""


class _RecordMapping(Mapping[str, Any]):
    """Small immutable-record adapter with read-only mapping ergonomics."""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())


@dataclass(frozen=True)
class CanonicalIdentityPermissions(_RecordMapping):
    canonical_build_allowed: bool
    canonical_refresh_allowed: bool
    reconciliation_allowed: bool
    applied_manifest_advance_allowed: bool
    trusted_current_claim_allowed: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "canonical_build_allowed": self.canonical_build_allowed,
            "canonical_refresh_allowed": self.canonical_refresh_allowed,
            "reconciliation_allowed": self.reconciliation_allowed,
            "applied_manifest_advance_allowed": (
                self.applied_manifest_advance_allowed
            ),
            "trusted_current_claim_allowed": (
                self.trusted_current_claim_allowed
            ),
        }


@dataclass(frozen=True)
class ConfirmationRecord(_RecordMapping):
    decision: str | None = None
    confirmed_at: str | None = None
    confirmed_by: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "confirmed_at": self.confirmed_at,
            "confirmed_by": self.confirmed_by,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MajorChangeRecord(_RecordMapping):
    candidate: bool = False
    detected_at: str | None = None
    signals: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    resolved_at: str | None = None
    resolution_decision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "detected_at": self.detected_at,
            "signals": list(self.signals),
            "evidence": list(self.evidence),
            "resolved_at": self.resolved_at,
            "resolution_decision": self.resolution_decision,
        }


@dataclass(frozen=True)
class ArchivedEpochRecord(_RecordMapping):
    identity_status: str
    architecture_epoch: int | None
    index_scope: str
    project_tag: str
    archived_at: str
    archived_by: str
    reason: str
    readable: bool = True
    writes_allowed: bool = False
    reconciliation_allowed: bool = False
    deleted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity_status": self.identity_status,
            "architecture_epoch": self.architecture_epoch,
            "index_scope": self.index_scope,
            "project_tag": self.project_tag,
            "archived_at": self.archived_at,
            "archived_by": self.archived_by,
            "reason": self.reason,
            "readable": self.readable,
            "writes_allowed": self.writes_allowed,
            "reconciliation_allowed": self.reconciliation_allowed,
            "deleted": self.deleted,
        }


@dataclass(frozen=True)
class LegacyNamespaceWarning(_RecordMapping):
    namespace: str
    warning: str
    preserve: bool = True
    deletion_allowed: bool = False
    automatic_epoch_binding_allowed: bool = False
    recommended_phase: str = LEGACY_MIGRATION_PHASE

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "warning": self.warning,
            "preserve": self.preserve,
            "deletion_allowed": self.deletion_allowed,
            "automatic_epoch_binding_allowed": (
                self.automatic_epoch_binding_allowed
            ),
            "recommended_phase": self.recommended_phase,
        }


@dataclass(frozen=True)
class ActivationGraphIndependence(_RecordMapping):
    operation_allowed: bool = True
    allowed_identity_statuses: tuple[str, ...] = (
        ACTIVATION_ALLOWED_IDENTITY_STATUSES
    )
    may_confirm_project: bool = False
    may_create_architecture_epoch: bool = False
    may_advance_canonical_manifest: bool = False
    may_reconcile_canonical_rows: bool = False
    may_change_project_tag: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_allowed": self.operation_allowed,
            "allowed_identity_statuses": list(
                self.allowed_identity_statuses
            ),
            "may_confirm_project": self.may_confirm_project,
            "may_create_architecture_epoch": (
                self.may_create_architecture_epoch
            ),
            "may_advance_canonical_manifest": (
                self.may_advance_canonical_manifest
            ),
            "may_reconcile_canonical_rows": (
                self.may_reconcile_canonical_rows
            ),
            "may_change_project_tag": self.may_change_project_tag,
        }


@dataclass(frozen=True)
class RepositoryIdentityState(_RecordMapping):
    schema_version: int
    artifact_kind: str
    repository_id: str
    canonical_root: str
    storage_key: str
    identity_status: str
    project_tag: str | None
    previous_project_tag: str | None
    candidate_project_tag: str | None
    architecture_epoch: int | None
    active_index_scope: str
    previous_index_scope: str | None
    human_confirmation_required: bool
    confirmation: ConfirmationRecord
    major_change: MajorChangeRecord
    archived_epochs: tuple[ArchivedEpochRecord, ...]
    legacy_namespace_warnings: tuple[LegacyNamespaceWarning, ...]
    permissions: CanonicalIdentityPermissions
    activation_graph_independence: ActivationGraphIndependence
    permission_layer: str
    trusted_completion_required: bool
    trusted_completion_phase: str
    state_revision: int
    state_errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_kind": self.artifact_kind,
            "repository_id": self.repository_id,
            "canonical_root": self.canonical_root,
            "storage_key": self.storage_key,
            "identity_status": self.identity_status,
            "project_tag": self.project_tag,
            "previous_project_tag": self.previous_project_tag,
            "candidate_project_tag": self.candidate_project_tag,
            "architecture_epoch": self.architecture_epoch,
            "active_index_scope": self.active_index_scope,
            "previous_index_scope": self.previous_index_scope,
            "human_confirmation_required": (
                self.human_confirmation_required
            ),
            "confirmation": self.confirmation.to_dict(),
            "major_change": self.major_change.to_dict(),
            "archived_epochs": [
                record.to_dict() for record in self.archived_epochs
            ],
            "legacy_namespace_warnings": [
                warning.to_dict()
                for warning in self.legacy_namespace_warnings
            ],
            "permissions": self.permissions.to_dict(),
            "activation_graph_independence": (
                self.activation_graph_independence.to_dict()
            ),
            "permission_layer": self.permission_layer,
            "trusted_completion_required": (
                self.trusted_completion_required
            ),
            "trusted_completion_phase": self.trusted_completion_phase,
            "state_revision": self.state_revision,
            "state_errors": list(self.state_errors),
        }


@dataclass(frozen=True)
class HumanIdentityDecision(_RecordMapping):
    decision: str
    confirmed_at: str
    confirmed_by: str
    reason: str
    confirmed_project_tag: str | None = None
    new_architecture_epoch: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "confirmed_at": self.confirmed_at,
            "confirmed_by": self.confirmed_by,
            "reason": self.reason,
            "confirmed_project_tag": self.confirmed_project_tag,
            "new_architecture_epoch": self.new_architecture_epoch,
        }


@dataclass(frozen=True)
class MajorChangeDecision(_RecordMapping):
    valid: bool
    major_change_candidate: bool
    human_confirmation_required: bool
    signals: tuple[str, ...]
    evidence: tuple[str, ...]
    minimum_signal_count: int
    reason: str
    errors: tuple[str, ...] = ()
    automatically_create_new_epoch: bool = False
    automatically_classify_new_project: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "major_change_candidate": self.major_change_candidate,
            "human_confirmation_required": (
                self.human_confirmation_required
            ),
            "signals": list(self.signals),
            "evidence": list(self.evidence),
            "minimum_signal_count": self.minimum_signal_count,
            "reason": self.reason,
            "errors": list(self.errors),
            "automatically_create_new_epoch": (
                self.automatically_create_new_epoch
            ),
            "automatically_classify_new_project": (
                self.automatically_classify_new_project
            ),
        }


@dataclass(frozen=True)
class IdentityTransitionValidation(_RecordMapping):
    allowed: bool
    current_status: str
    target_status: str
    reason: str
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "current_status": self.current_status,
            "target_status": self.target_status,
            "reason": self.reason,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class IdentityTransitionResult(_RecordMapping):
    valid: bool
    applied: bool
    decision: str | None
    outcome: str
    state: RepositoryIdentityState
    reason: str
    errors: tuple[str, ...] = ()
    rebinding_required: bool = False
    archived_epoch: ArchivedEpochRecord | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "applied": self.applied,
            "decision": self.decision,
            "outcome": self.outcome,
            "state": self.state.to_dict(),
            "reason": self.reason,
            "errors": list(self.errors),
            "rebinding_required": self.rebinding_required,
            "archived_epoch": (
                self.archived_epoch.to_dict()
                if self.archived_epoch is not None
                else None
            ),
        }


@dataclass(frozen=True)
class IdentityStateValidation(_RecordMapping):
    valid: bool
    effective_status: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "effective_status": self.effective_status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class IdentityStateLoadResult(_RecordMapping):
    exists: bool
    valid: bool
    status: str
    path: str
    state: RepositoryIdentityState
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def identity_status(self) -> str:
        return self.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "exists": self.exists,
            "valid": self.valid,
            "status": self.status,
            "path": self.path,
            "state": self.state.to_dict(),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class IdentityStateSaveResult(_RecordMapping):
    ok: bool
    path: str
    state: RepositoryIdentityState
    previous_revision: int
    revision: int
    replaced: bool
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "path": self.path,
            "state": self.state.to_dict(),
            "previous_revision": self.previous_revision,
            "revision": self.revision,
            "replaced": self.replaced,
            "errors": list(self.errors),
        }


def _all_false_permissions() -> CanonicalIdentityPermissions:
    return CanonicalIdentityPermissions(False, False, False, False, False)


def _coerce_identity(
    identity_or_repo: RepositoryIdentity | str | os.PathLike[str],
) -> RepositoryIdentity:
    if isinstance(identity_or_repo, RepositoryIdentity):
        rebuilt = build_repository_identity(
            identity_or_repo.canonical_root,
            project_tag=identity_or_repo.project_tag,
            architecture_epoch=identity_or_repo.architecture_epoch,
        )
        if rebuilt != identity_or_repo:
            raise IdentityStateError(
                "RepositoryIdentity fields do not match its canonical_root"
            )
        return rebuilt
    return build_repository_identity(identity_or_repo)


def _normalize_epoch(
    value: Any,
    *,
    field: str,
    allow_baseline: bool,
) -> int | None:
    if value is None and allow_baseline:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > MAX_ARCHITECTURE_EPOCH
    ):
        baseline = " or None for the compatibility baseline" if allow_baseline else ""
        raise IdentityStateError(
            f"{field} must be a positive integer no greater than "
            f"{MAX_ARCHITECTURE_EPOCH}{baseline}"
        )
    return value


def _normalize_project_tag(
    value: Any,
    *,
    field: str,
    allow_none: bool,
) -> str | None:
    if value is None:
        if allow_none:
            return None
        raise IdentityStateError(f"{field} must be a confirmed nonblank label")
    if not isinstance(value, str):
        raise IdentityStateError(f"{field} must be text")
    normalized = value.strip()
    if not normalized:
        if allow_none:
            return None
        raise IdentityStateError(f"{field} must be a confirmed nonblank label")
    if len(normalized) > MAX_PROJECT_TAG_LENGTH:
        raise IdentityStateError(
            f"{field} exceeds {MAX_PROJECT_TAG_LENGTH} characters"
        )
    if (
        _CONTROL_CHARACTER_RE.search(normalized)
        or "/" in normalized
        or "\\" in normalized
        or _CREDENTIAL_ASSIGNMENT_RE.search(normalized)
        or _CREDENTIAL_URL_RE.search(normalized)
    ):
        raise IdentityStateError(f"{field} is unsafe for persistent state")
    return normalized


def _normalize_safe_text(
    value: Any,
    *,
    field: str,
    maximum: int,
    allow_none: bool = False,
) -> str | None:
    if value is None:
        if allow_none:
            return None
        raise IdentityStateError(f"{field} is required")
    if not isinstance(value, str):
        raise IdentityStateError(f"{field} must be text")
    normalized = value.strip()
    if not normalized:
        if allow_none:
            return None
        raise IdentityStateError(f"{field} must not be blank")
    if len(normalized) > maximum:
        raise IdentityStateError(
            f"{field} exceeds the {maximum}-character persistence bound"
        )
    if (
        _CONTROL_CHARACTER_RE.search(normalized)
        or _CREDENTIAL_ASSIGNMENT_RE.search(normalized)
        or _CREDENTIAL_URL_RE.search(normalized)
    ):
        raise IdentityStateError(
            f"{field} appears to contain credential material"
        )
    return normalized


def _normalize_timestamp(value: Any, *, field: str) -> str:
    normalized = _normalize_safe_text(
        value,
        field=field,
        maximum=128,
    )
    assert normalized is not None
    raw = normalized[:-1] + "+00:00" if normalized.endswith(("Z", "z")) else normalized
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise IdentityStateError(
            f"{field} must be a timezone-aware ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IdentityStateError(
            f"{field} must be a timezone-aware ISO timestamp"
        )
    return normalized


def _timestamp_instant(value: Any, *, field: str) -> datetime:
    normalized = _normalize_timestamp(value, field=field)
    raw = (
        normalized[:-1] + "+00:00"
        if normalized.endswith(("Z", "z"))
        else normalized
    )
    return datetime.fromisoformat(raw)


def _normalize_human_actor(value: Any) -> str:
    actor = _normalize_safe_text(
        value,
        field="confirmed_by",
        maximum=128,
    )
    assert actor is not None
    folded = actor.casefold()
    if folded != "human" and not folded.startswith("human:"):
        raise IdentityStateError(
            "confirmed_by must explicitly identify a human actor"
        )
    return actor


def _as_bounded_sequence(
    values: Any,
    *,
    field: str,
    maximum_count: int,
) -> tuple[Any, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes, bytearray)):
        result = (values,)
    elif isinstance(values, Sequence):
        result = tuple(values)
    else:
        raise IdentityStateError(f"{field} must be a bounded sequence")
    if len(result) > maximum_count:
        raise IdentityStateError(
            f"{field} exceeds the {maximum_count}-item bound"
        )
    return result


def _normalize_evidence(
    values: Any,
    *,
    field: str = "evidence",
) -> tuple[str, ...]:
    normalized: set[str] = set()
    for index, value in enumerate(
        _as_bounded_sequence(
            values,
            field=field,
            maximum_count=MAX_EVIDENCE_COUNT,
        )
    ):
        text = _normalize_safe_text(
            value,
            field=f"{field}[{index}]",
            maximum=MAX_EVIDENCE_LENGTH,
        )
        assert text is not None
        normalized.add(text)
    return tuple(sorted(normalized))


def _legacy_namespace_warnings(
    evidence: Any,
) -> tuple[LegacyNamespaceWarning, ...]:
    values = _as_bounded_sequence(
        evidence,
        field="legacy_namespace_evidence",
        maximum_count=MAX_LEGACY_NAMESPACE_COUNT,
    )
    namespaces: set[str] = set()
    for index, value in enumerate(values):
        namespace = _normalize_safe_text(
            value,
            field=f"legacy_namespace_evidence[{index}]",
            maximum=MAX_LEGACY_NAMESPACE_LENGTH,
        )
        assert namespace is not None
        namespaces.add(namespace)
    return tuple(
        LegacyNamespaceWarning(
            namespace=namespace,
            warning=LEGACY_NAMESPACE_WARNING_TEXT,
        )
        for namespace in sorted(namespaces)
    )


def activation_graph_identity_independence_metadata(
) -> ActivationGraphIndependence:
    """Return test-pinned proof that Activation work has no identity power."""
    return ActivationGraphIndependence()


def _abstract_permissions_for_status(
    status: str,
) -> CanonicalIdentityPermissions:
    if status != IDENTITY_STATUS_CONFIRMED:
        return _all_false_permissions()
    return CanonicalIdentityPermissions(
        canonical_build_allowed=True,
        canonical_refresh_allowed=True,
        reconciliation_allowed=True,
        applied_manifest_advance_allowed=True,
        trusted_current_claim_allowed=False,
    )


def _confirmed_state_authority_ready(
    state: RepositoryIdentityState,
) -> bool:
    """Check the fields that establish confirmed identity authority.

    Persisted ``permissions`` are deliberately excluded: this helper derives
    them. Full artifact validation separately checks that the persisted copy
    equals this result.
    """
    if not (
        isinstance(state.confirmation, ConfirmationRecord)
        and isinstance(state.major_change, MajorChangeRecord)
        and isinstance(state.permissions, CanonicalIdentityPermissions)
        and isinstance(
            state.activation_graph_independence,
            ActivationGraphIndependence,
        )
    ):
        return False
    try:
        epoch = _normalize_epoch(
            state.architecture_epoch,
            field="architecture_epoch",
            allow_baseline=True,
        )
        expected_scope = derive_repository_index_scope_from_id(
            state.repository_id,
            architecture_epoch=epoch,
        )
        expected_storage_key = derive_repository_storage_key_from_id(
            state.repository_id
        )
        tag = _normalize_project_tag(
            state.project_tag,
            field="project_tag",
            allow_none=False,
        )
        confirmation_errors = _validate_confirmation_record(
            state.confirmation
        )
    except (IdentityStateError, TypeError, ValueError):
        return False
    return (
        type(state.schema_version) is int
        and state.schema_version == SCHEMA_VERSION
        and state.artifact_kind == ARTIFACT_KIND
        and is_repository_id(state.repository_id)
        and state.storage_key == expected_storage_key
        and state.active_index_scope == expected_scope
        and is_code_index_scope(state.active_index_scope)
        and state.identity_status == IDENTITY_STATUS_CONFIRMED
        and tag is not None
        and state.human_confirmation_required is False
        and type(state.major_change.candidate) is bool
        and state.major_change.candidate is False
        and not confirmation_errors
        and state.confirmation.decision
        in {
            DECISION_SAME_PROJECT,
            DECISION_NEW_ARCHITECTURE_EPOCH,
        }
        and state.permission_layer == PERMISSION_LAYER
        and state.trusted_completion_required is True
        and state.trusted_completion_phase == TRUSTED_COMPLETION_PHASE
        and not state.state_errors
    )


def derive_canonical_identity_permissions(
    identity_state: RepositoryIdentityState | Mapping[str, Any] | str | None,
) -> CanonicalIdentityPermissions:
    """Derive identity-only canonical permissions without completion evidence.

    Only a complete, structurally valid state record can grant authority.
    Status-only matrix rows are exposed separately by
    :func:`identity_permission_matrix`.
    """
    if isinstance(identity_state, RepositoryIdentityState):
        candidate = identity_state
    elif isinstance(identity_state, Mapping):
        try:
            candidate = _state_from_mapping(
                copy.deepcopy(dict(identity_state))
            )
        except (
            IdentityStateError,
            RecursionError,
            TypeError,
            ValueError,
        ):
            return _all_false_permissions()
    else:
        return _all_false_permissions()
    if not _confirmed_state_authority_ready(candidate):
        return _all_false_permissions()
    expected = _abstract_permissions_for_status(
        candidate.identity_status
    )
    if (
        any(
            type(value) is not bool
            for value in candidate.permissions.to_dict().values()
        )
        or candidate.permissions != expected
    ):
        return _all_false_permissions()
    validation = validate_repository_identity_state(candidate)
    if not validation.valid:
        return _all_false_permissions()
    return expected


def identity_permission_matrix() -> tuple[dict[str, Any], ...]:
    """Return all stable identity statuses and their explicit permissions."""
    return tuple(
        {
            "identity_status": status,
            **_abstract_permissions_for_status(status).to_dict(),
            "activation_graph_operation_allowed": (
                status in ACTIVATION_ALLOWED_IDENTITY_STATUSES
                or status
                in {
                    IDENTITY_STATUS_CONFIRMED,
                    IDENTITY_STATUS_ARCHIVED,
                }
            ),
            "permission_layer": PERMISSION_LAYER,
            "trusted_completion_required": True,
        }
        for status in IDENTITY_STATUSES
    )


def _state_with_derived_permissions(
    state: RepositoryIdentityState,
) -> RepositoryIdentityState:
    expected = _abstract_permissions_for_status(
        state.identity_status
    )
    candidate = replace(
        state,
        permissions=expected,
    )
    validation = validate_repository_identity_state(candidate)
    if candidate.identity_status == IDENTITY_STATUS_CONFIRMED and (
        not validation.valid
    ):
        return replace(state, permissions=_all_false_permissions())
    return candidate


def _base_state(
    identity: RepositoryIdentity,
    *,
    status: str,
    architecture_epoch: int | None,
    revision: int,
    candidate_project_tag: str | None = None,
    legacy_namespace_warnings: tuple[
        LegacyNamespaceWarning, ...
    ] = (),
    state_errors: tuple[str, ...] = (),
) -> RepositoryIdentityState:
    scope = derive_repository_index_scope_from_id(
        identity.repository_id,
        architecture_epoch=architecture_epoch,
    )
    state = RepositoryIdentityState(
        schema_version=SCHEMA_VERSION,
        artifact_kind=ARTIFACT_KIND,
        repository_id=identity.repository_id,
        canonical_root=identity.canonical_root,
        storage_key=identity.storage_key,
        identity_status=status,
        project_tag=None,
        previous_project_tag=None,
        candidate_project_tag=candidate_project_tag,
        architecture_epoch=architecture_epoch,
        active_index_scope=scope,
        previous_index_scope=None,
        human_confirmation_required=status
        in {
            IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED,
            IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED,
            IDENTITY_STATUS_BLOCKED,
        },
        confirmation=ConfirmationRecord(),
        major_change=MajorChangeRecord(),
        archived_epochs=(),
        legacy_namespace_warnings=legacy_namespace_warnings,
        permissions=_all_false_permissions(),
        activation_graph_independence=(
            activation_graph_identity_independence_metadata()
        ),
        permission_layer=PERMISSION_LAYER,
        trusted_completion_required=True,
        trusted_completion_phase=TRUSTED_COMPLETION_PHASE,
        state_revision=revision,
        state_errors=state_errors,
    )
    return _state_with_derived_permissions(state)


def build_uninitialized_identity_state(
    identity_or_repo: RepositoryIdentity | str | os.PathLike[str],
) -> RepositoryIdentityState:
    """Build an in-memory missing-artifact view; never persist this status."""
    identity = _coerce_identity(identity_or_repo)
    return _base_state(
        identity,
        status=IDENTITY_STATUS_UNINITIALIZED,
        architecture_epoch=None,
        revision=0,
    )


def initialize_repository_identity_state(
    identity_or_repo: RepositoryIdentity | str | os.PathLike[str],
    *,
    candidate_project_tag: str | None = None,
    architecture_epoch: int | None = None,
    legacy_namespace_evidence: Sequence[str] = (),
) -> RepositoryIdentityState:
    """Build the first persistable, still-unconfirmed identity record."""
    identity = _coerce_identity(identity_or_repo)
    epoch = _normalize_epoch(
        architecture_epoch,
        field="architecture_epoch",
        allow_baseline=True,
    )
    if epoch is not None or identity.architecture_epoch is not None:
        raise IdentityStateError(
            "initial identity state must use the compatibility baseline; "
            "later epochs require major-change review and an explicit "
            "new_architecture_epoch human decision"
        )
    candidate_source = (
        candidate_project_tag
        if candidate_project_tag is not None
        else identity.project_tag
    )
    candidate = _normalize_project_tag(
        candidate_source,
        field="candidate_project_tag",
        allow_none=True,
    )
    warnings = _legacy_namespace_warnings(
        copy.deepcopy(legacy_namespace_evidence)
    )
    return _base_state(
        identity,
        status=IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED,
        architecture_epoch=epoch,
        revision=1,
        candidate_project_tag=candidate,
        legacy_namespace_warnings=warnings,
    )


def append_legacy_namespace_warnings(
    state: RepositoryIdentityState,
    evidence: Sequence[str],
) -> IdentityTransitionResult:
    """Record newly supplied legacy namespaces without binding or mutation."""
    if not isinstance(state, RepositoryIdentityState):
        raise TypeError("state must be RepositoryIdentityState")
    validation = validate_repository_identity_state(state)
    if not validation.valid:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=None,
            outcome="invalid_transition",
            state=state,
            reason="Legacy warnings cannot be added to an invalid state.",
            errors=validation.errors,
        )
    if state.identity_status not in {
        IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED,
        IDENTITY_STATUS_CONFIRMED,
        IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED,
    }:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=None,
            outcome="invalid_transition",
            state=state,
            reason=(
                "Legacy warnings may be recorded only on an active persisted "
                "identity state."
            ),
            errors=("source identity status cannot accept legacy warnings",),
        )
    try:
        supplied = _legacy_namespace_warnings(copy.deepcopy(evidence))
        by_namespace = {
            warning.namespace: warning
            for warning in state.legacy_namespace_warnings
        }
        for warning in supplied:
            by_namespace.setdefault(warning.namespace, warning)
        if len(by_namespace) > MAX_LEGACY_NAMESPACE_COUNT:
            raise IdentityStateError(
                "combined legacy namespace warnings exceed the "
                f"{MAX_LEGACY_NAMESPACE_COUNT}-item bound"
            )
        combined = tuple(
            by_namespace[namespace]
            for namespace in sorted(by_namespace)
        )
    except IdentityStateError as exc:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=None,
            outcome="invalid_legacy_namespace_evidence",
            state=state,
            reason="Legacy namespace evidence could not be recorded safely.",
            errors=(str(exc),),
        )
    if combined == state.legacy_namespace_warnings:
        return IdentityTransitionResult(
            valid=True,
            applied=False,
            decision=None,
            outcome="legacy_namespace_warnings_unchanged",
            state=state,
            reason="All supplied legacy namespaces were already recorded.",
        )
    target = replace(
        state,
        legacy_namespace_warnings=combined,
        state_revision=state.state_revision + 1,
    )
    transition = validate_identity_state_transition(state, target)
    return IdentityTransitionResult(
        valid=transition.allowed,
        applied=transition.allowed,
        decision=None,
        outcome=(
            "legacy_namespace_warnings_recorded"
            if transition.allowed
            else "invalid_transition"
        ),
        state=target if transition.allowed else state,
        reason=transition.reason,
        errors=transition.errors,
    )


def _normalize_signal_id(value: Any) -> str:
    signal = _normalize_safe_text(
        value,
        field="signal_id",
        maximum=128,
    )
    assert signal is not None
    canonical = _MAJOR_CHANGE_SIGNAL_ALIASES.get(signal, signal)
    if canonical not in MAJOR_CHANGE_SIGNAL_IDS:
        raise IdentityStateError(
            f"unsupported major-change signal: {signal!r}"
        )
    return canonical


def classify_major_change_candidate(
    *,
    signals: Sequence[Any],
    thresholds: Mapping[str, Any] | None = None,
) -> MajorChangeDecision:
    """Classify supplied evidence without scanning, models, or side effects."""
    errors: list[str] = []
    normalized_signals: set[str] = set()
    normalized_evidence: set[str] = set()
    try:
        signal_items = _as_bounded_sequence(
            copy.deepcopy(signals),
            field="signals",
            maximum_count=MAX_SIGNAL_COUNT,
        )
        for index, item in enumerate(signal_items):
            if isinstance(item, Mapping):
                unknown = set(item) - {"signal_id", "id", "evidence"}
                if unknown:
                    raise IdentityStateError(
                        f"signals[{index}] has unsupported fields: "
                        f"{', '.join(sorted(str(key) for key in unknown))}"
                    )
                signal_value = item.get("signal_id", item.get("id"))
                normalized_signals.add(_normalize_signal_id(signal_value))
                normalized_evidence.update(
                    _normalize_evidence(
                        item.get("evidence"),
                        field=f"signals[{index}].evidence",
                    )
                )
            else:
                normalized_signals.add(_normalize_signal_id(item))
        if len(normalized_evidence) > MAX_EVIDENCE_COUNT:
            raise IdentityStateError(
                f"combined signal evidence exceeds the "
                f"{MAX_EVIDENCE_COUNT}-item bound"
            )

        minimum_signal_count = 2
        force_signal_ids = {SIGNAL_MANUAL_OPERATOR_FLAG}
        if thresholds is not None:
            if not isinstance(thresholds, Mapping):
                raise IdentityStateError("thresholds must be a mapping")
            unknown_thresholds = set(thresholds) - {
                "minimum_signal_count",
                "force_signal_ids",
            }
            if unknown_thresholds:
                raise IdentityStateError(
                    "thresholds has unsupported fields: "
                    + ", ".join(
                        sorted(str(key) for key in unknown_thresholds)
                    )
                )
            if "minimum_signal_count" in thresholds:
                raw_minimum = thresholds["minimum_signal_count"]
                if (
                    isinstance(raw_minimum, bool)
                    or not isinstance(raw_minimum, int)
                    or raw_minimum <= 0
                    or raw_minimum > len(MAJOR_CHANGE_SIGNAL_IDS)
                ):
                    raise IdentityStateError(
                        "minimum_signal_count must be a positive bounded integer"
                    )
                minimum_signal_count = raw_minimum
            if "force_signal_ids" in thresholds:
                force_signal_ids = {
                    _normalize_signal_id(value)
                    for value in _as_bounded_sequence(
                        thresholds["force_signal_ids"],
                        field="force_signal_ids",
                        maximum_count=len(MAJOR_CHANGE_SIGNAL_IDS),
                    )
                }
    except IdentityStateError as exc:
        errors.append(str(exc))
        return MajorChangeDecision(
            valid=False,
            major_change_candidate=False,
            human_confirmation_required=False,
            signals=tuple(sorted(normalized_signals)),
            evidence=tuple(sorted(normalized_evidence))[
                :MAX_EVIDENCE_COUNT
            ],
            minimum_signal_count=2,
            reason="Invalid major-change evidence fails closed.",
            errors=tuple(sorted(set(errors))),
        )

    candidate = bool(normalized_signals & force_signal_ids) or (
        len(normalized_signals) >= minimum_signal_count
    )
    if candidate:
        reason = (
            "A manual operator signal requires human confirmation."
            if normalized_signals & force_signal_ids
            else (
                f"{len(normalized_signals)} independent supplied signals "
                f"meet the policy threshold of {minimum_signal_count}."
            )
        )
    else:
        reason = (
            f"{len(normalized_signals)} supplied signal(s) do not meet the "
            f"policy threshold of {minimum_signal_count}; no state transition "
            "is inferred."
        )
    return MajorChangeDecision(
        valid=True,
        major_change_candidate=candidate,
        human_confirmation_required=candidate,
        signals=tuple(sorted(normalized_signals)),
        evidence=tuple(sorted(normalized_evidence)),
        minimum_signal_count=minimum_signal_count,
        reason=reason,
    )


def apply_major_change_candidate(
    state: RepositoryIdentityState,
    decision: MajorChangeDecision,
    *,
    detected_at: str,
    evidence: Sequence[str] = (),
) -> IdentityTransitionResult:
    """Apply only a positive advisory decision to a confirmed identity."""
    if not isinstance(state, RepositoryIdentityState):
        raise TypeError("state must be RepositoryIdentityState")
    if state.identity_status != IDENTITY_STATUS_CONFIRMED:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=None,
            outcome="invalid_transition",
            state=state,
            reason="Only a confirmed identity can enter major-change review.",
            errors=("source identity status is not confirmed",),
        )
    if not decision.valid:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=None,
            outcome="invalid_evidence",
            state=state,
            reason=decision.reason,
            errors=decision.errors,
        )
    if not decision.major_change_candidate:
        return IdentityTransitionResult(
            valid=True,
            applied=False,
            decision=None,
            outcome="no_major_change_candidate",
            state=state,
            reason=decision.reason,
        )
    try:
        timestamp = _normalize_timestamp(
            detected_at,
            field="detected_at",
        )
        combined_evidence = tuple(
            sorted(
                set(decision.evidence)
                | set(_normalize_evidence(copy.deepcopy(evidence)))
            )
        )
        if len(combined_evidence) > MAX_EVIDENCE_COUNT:
            raise IdentityStateError(
                f"combined major-change evidence exceeds the "
                f"{MAX_EVIDENCE_COUNT}-item bound"
            )
    except IdentityStateError as exc:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=None,
            outcome="invalid_evidence",
            state=state,
            reason="Major-change evidence could not be persisted safely.",
            errors=(str(exc),),
        )
    target = replace(
        state,
        identity_status=IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED,
        human_confirmation_required=True,
        major_change=MajorChangeRecord(
            candidate=True,
            detected_at=timestamp,
            signals=decision.signals,
            evidence=combined_evidence,
        ),
        state_revision=state.state_revision + 1,
    )
    target = _state_with_derived_permissions(target)
    validation = validate_identity_state_transition(state, target)
    return IdentityTransitionResult(
        valid=validation.allowed,
        applied=validation.allowed,
        decision=None,
        outcome=(
            IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED
            if validation.allowed
            else "invalid_transition"
        ),
        state=target if validation.allowed else state,
        reason=validation.reason,
        errors=validation.errors,
    )


def declare_major_change_candidate(
    state: RepositoryIdentityState,
    decision: MajorChangeDecision,
    *,
    detected_at: str,
    evidence: Sequence[str] = (),
) -> IdentityTransitionResult:
    """Compatibility alias for :func:`apply_major_change_candidate`."""
    return apply_major_change_candidate(
        state,
        decision,
        detected_at=detected_at,
        evidence=evidence,
    )


def _coerce_human_decision(
    decision: HumanIdentityDecision | str,
    *,
    confirmed_at: str | None,
    confirmed_by: str | None,
    reason: str | None,
    confirmed_project_tag: str | None,
    new_architecture_epoch: int | None,
) -> HumanIdentityDecision:
    if isinstance(decision, HumanIdentityDecision):
        if any(
            value is not None
            for value in (
                confirmed_at,
                confirmed_by,
                reason,
                confirmed_project_tag,
                new_architecture_epoch,
            )
        ):
            raise IdentityStateError(
                "decision object cannot be combined with decision keyword fields"
            )
        source = decision
    elif isinstance(decision, str):
        source = HumanIdentityDecision(
            decision=decision,
            confirmed_at=confirmed_at or "",
            confirmed_by=confirmed_by or "",
            reason=reason or "",
            confirmed_project_tag=confirmed_project_tag,
            new_architecture_epoch=new_architecture_epoch,
        )
    else:
        raise IdentityStateError("an explicit human decision is required")

    if source.decision not in HUMAN_IDENTITY_DECISIONS:
        raise IdentityStateError(
            f"unsupported human identity decision: {source.decision!r}"
        )
    timestamp = _normalize_timestamp(
        source.confirmed_at,
        field="confirmed_at",
    )
    actor = _normalize_human_actor(source.confirmed_by)
    normalized_reason = _normalize_safe_text(
        source.reason,
        field="reason",
        maximum=MAX_REASON_LENGTH,
    )
    assert normalized_reason is not None
    tag = _normalize_project_tag(
        source.confirmed_project_tag,
        field="confirmed_project_tag",
        allow_none=True,
    )
    epoch = source.new_architecture_epoch
    if source.decision == DECISION_NEW_ARCHITECTURE_EPOCH:
        epoch = _normalize_epoch(
            epoch,
            field="new_architecture_epoch",
            allow_baseline=False,
        )
    elif epoch is not None:
        raise IdentityStateError(
            "new_architecture_epoch is valid only for that explicit decision"
        )
    return HumanIdentityDecision(
        decision=source.decision,
        confirmed_at=timestamp,
        confirmed_by=actor,
        reason=normalized_reason,
        confirmed_project_tag=tag,
        new_architecture_epoch=epoch,
    )


def _resolved_major_change(
    record: MajorChangeRecord,
    *,
    decision: HumanIdentityDecision,
) -> MajorChangeRecord:
    if not record.candidate:
        return record
    return replace(
        record,
        candidate=False,
        resolved_at=decision.confirmed_at,
        resolution_decision=decision.decision,
    )


def apply_human_identity_decision(
    state: RepositoryIdentityState,
    decision: HumanIdentityDecision | str,
    *,
    confirmed_at: str | None = None,
    confirmed_by: str | None = None,
    reason: str | None = None,
    confirmed_project_tag: str | None = None,
    new_architecture_epoch: int | None = None,
) -> IdentityTransitionResult:
    """Apply one explicit human decision without mutating the source state."""
    if not isinstance(state, RepositoryIdentityState):
        raise TypeError("state must be RepositoryIdentityState")
    try:
        human = _coerce_human_decision(
            decision,
            confirmed_at=confirmed_at,
            confirmed_by=confirmed_by,
            reason=reason,
            confirmed_project_tag=confirmed_project_tag,
            new_architecture_epoch=new_architecture_epoch,
        )
    except IdentityStateError as exc:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=(
                decision.decision
                if isinstance(decision, HumanIdentityDecision)
                else str(decision) if decision is not None else None
            ),
            outcome="invalid_human_decision",
            state=state,
            reason="The human decision record is incomplete or unsafe.",
            errors=(str(exc),),
        )

    if state.identity_status in {
        IDENTITY_STATUS_ARCHIVED,
        IDENTITY_STATUS_BLOCKED,
        IDENTITY_STATUS_UNINITIALIZED,
    }:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=human.decision,
            outcome="invalid_transition",
            state=state,
            reason=(
                f"{state.identity_status} cannot transition through an "
                "ordinary confirmation decision."
            ),
            errors=("source state is terminal or not initialized",),
        )
    if state.identity_status not in {
        IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED,
        IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED,
    }:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=human.decision,
            outcome="invalid_transition",
            state=state,
            reason="No human identity confirmation is currently pending.",
            errors=("human confirmation is not required by the source state",),
        )

    if human.decision == DECISION_NEW_PROJECT:
        return IdentityTransitionResult(
            valid=True,
            applied=False,
            decision=human.decision,
            outcome="repository_identity_rebinding_required",
            state=state,
            reason=(
                "The directory may represent a different semantic project. "
                "Rebinding requires a later explicit workflow; no identity, "
                "scope, artifact, or database row was changed."
            ),
            rebinding_required=True,
        )
    if human.decision == DECISION_REJECT_OR_DEFER:
        return IdentityTransitionResult(
            valid=True,
            applied=False,
            decision=human.decision,
            outcome="confirmation_deferred",
            state=state,
            reason=(
                "Canonical mutation remains locked. Activation Graph work "
                "remains independently available."
            ),
        )

    if human.decision == DECISION_SAME_PROJECT:
        try:
            if (
                state.identity_status
                == IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED
            ):
                # A candidate label is deliberately never inferred.
                tag = _normalize_project_tag(
                    human.confirmed_project_tag,
                    field="confirmed_project_tag",
                    allow_none=False,
                )
            else:
                tag = _normalize_project_tag(
                    (
                        human.confirmed_project_tag
                        if human.confirmed_project_tag is not None
                        else state.project_tag
                    ),
                    field="confirmed_project_tag",
                    allow_none=False,
                )
        except IdentityStateError as exc:
            return IdentityTransitionResult(
                valid=False,
                applied=False,
                decision=human.decision,
                outcome="invalid_human_decision",
                state=state,
                reason=(
                    "same_project requires an explicitly confirmed semantic "
                    "label for the initial confirmation."
                ),
                errors=(str(exc),),
            )
        target = replace(
            state,
            identity_status=IDENTITY_STATUS_CONFIRMED,
            project_tag=tag,
            previous_project_tag=(
                state.project_tag
                if state.project_tag is not None and state.project_tag != tag
                else state.previous_project_tag
            ),
            candidate_project_tag=None,
            human_confirmation_required=False,
            confirmation=ConfirmationRecord(
                decision=human.decision,
                confirmed_at=human.confirmed_at,
                confirmed_by=human.confirmed_by,
                reason=human.reason,
            ),
            major_change=_resolved_major_change(
                state.major_change,
                decision=human,
            ),
            state_revision=state.state_revision + 1,
        )
        target = _state_with_derived_permissions(target)
        validation = validate_identity_state_transition(state, target)
        return IdentityTransitionResult(
            valid=validation.allowed,
            applied=validation.allowed,
            decision=human.decision,
            outcome=(
                IDENTITY_STATUS_CONFIRMED
                if validation.allowed
                else "invalid_transition"
            ),
            state=target if validation.allowed else state,
            reason=validation.reason,
            errors=validation.errors,
        )

    # Only a pending major-change review may create a later epoch.
    if (
        state.identity_status
        != IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED
    ):
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=human.decision,
            outcome="invalid_transition",
            state=state,
            reason=(
                "A new architecture epoch is valid only while a major-change "
                "confirmation is pending."
            ),
            errors=("automatic or initial epoch creation is forbidden",),
        )
    assert human.decision == DECISION_NEW_ARCHITECTURE_EPOCH
    requested_epoch = human.new_architecture_epoch
    assert requested_epoch is not None
    expected_epoch = (
        1
        if state.architecture_epoch is None
        else state.architecture_epoch + 1
    )
    if requested_epoch != expected_epoch:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=human.decision,
            outcome="invalid_epoch",
            state=state,
            reason=(
                f"The explicit next architecture epoch must be "
                f"{expected_epoch}; received {requested_epoch}."
            ),
            errors=("architecture epoch is not the explicit next increment",),
        )
    try:
        tag = _normalize_project_tag(
            (
                human.confirmed_project_tag
                if human.confirmed_project_tag is not None
                else state.project_tag
            ),
            field="confirmed_project_tag",
            allow_none=False,
        )
        new_scope = derive_repository_index_scope_from_id(
            state.repository_id,
            architecture_epoch=requested_epoch,
        )
    except (IdentityStateError, ValueError) as exc:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=human.decision,
            outcome="invalid_epoch",
            state=state,
            reason="The requested epoch cannot establish a safe new scope.",
            errors=(str(exc),),
        )
    if new_scope == state.active_index_scope:
        return IdentityTransitionResult(
            valid=False,
            applied=False,
            decision=human.decision,
            outcome="invalid_epoch",
            state=state,
            reason="A new epoch must derive a distinct index scope.",
            errors=("requested epoch aliases the active index scope",),
        )
    assert state.project_tag is not None
    archived = ArchivedEpochRecord(
        identity_status=IDENTITY_STATUS_ARCHIVED,
        architecture_epoch=state.architecture_epoch,
        index_scope=state.active_index_scope,
        project_tag=state.project_tag,
        archived_at=human.confirmed_at,
        archived_by=human.confirmed_by,
        reason=human.reason,
    )
    target = replace(
        state,
        identity_status=IDENTITY_STATUS_CONFIRMED,
        project_tag=tag,
        previous_project_tag=state.project_tag,
        candidate_project_tag=None,
        architecture_epoch=requested_epoch,
        active_index_scope=new_scope,
        previous_index_scope=state.active_index_scope,
        human_confirmation_required=False,
        confirmation=ConfirmationRecord(
            decision=human.decision,
            confirmed_at=human.confirmed_at,
            confirmed_by=human.confirmed_by,
            reason=human.reason,
        ),
        major_change=_resolved_major_change(
            state.major_change,
            decision=human,
        ),
        archived_epochs=state.archived_epochs + (archived,),
        state_revision=state.state_revision + 1,
    )
    target = _state_with_derived_permissions(target)
    validation = validate_identity_state_transition(state, target)
    return IdentityTransitionResult(
        valid=validation.allowed,
        applied=validation.allowed,
        decision=human.decision,
        outcome=(
            "new_architecture_epoch_confirmed"
            if validation.allowed
            else "invalid_transition"
        ),
        state=target if validation.allowed else state,
        reason=validation.reason,
        errors=validation.errors,
        archived_epoch=archived if validation.allowed else None,
    )


def validate_human_identity_decision(
    state: RepositoryIdentityState,
    decision: HumanIdentityDecision,
) -> IdentityTransitionResult:
    """Pure validation preview; it performs no persistence or other mutation."""
    return apply_human_identity_decision(state, decision)


def _same_physical_identity(
    current: RepositoryIdentityState,
    target: RepositoryIdentityState,
) -> bool:
    return (
        current.repository_id == target.repository_id
        and current.canonical_root == target.canonical_root
        and current.storage_key == target.storage_key
    )


def validate_identity_state_transition(
    current: RepositoryIdentityState | None,
    target: RepositoryIdentityState,
) -> IdentityTransitionValidation:
    """Validate one deterministic persisted transition without side effects."""
    if not isinstance(target, RepositoryIdentityState):
        return IdentityTransitionValidation(
            allowed=False,
            current_status=(
                current.identity_status
                if isinstance(current, RepositoryIdentityState)
                else IDENTITY_STATUS_UNINITIALIZED
            ),
            target_status=IDENTITY_STATUS_BLOCKED,
            reason="Transition is forbidden by the identity-state contract.",
            errors=("target state must be RepositoryIdentityState",),
        )
    current_status = (
        current.identity_status
        if isinstance(current, RepositoryIdentityState)
        else IDENTITY_STATUS_UNINITIALIZED
    )
    target_status = target.identity_status
    errors: list[str] = []

    target_validation = validate_repository_identity_state(target)
    if not target_validation.valid:
        return IdentityTransitionValidation(
            allowed=False,
            current_status=current_status,
            target_status=target_status,
            reason="Transition is forbidden by the identity-state contract.",
            errors=target_validation.errors,
        )
    if current is None:
        if target_status != IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED:
            errors.append(
                "uninitialized may transition only to "
                "initial_confirmation_required"
            )
        if target.state_revision != 1:
            errors.append("initial persisted state revision must be 1")
        if (
            target.architecture_epoch is not None
            or target.previous_index_scope is not None
            or target.previous_project_tag is not None
            or target.archived_epochs
            or target.major_change != MajorChangeRecord()
        ):
            errors.append(
                "first persisted state must use the history-free "
                "compatibility baseline"
            )
    else:
        if not isinstance(current, RepositoryIdentityState):
            return IdentityTransitionValidation(
                allowed=False,
                current_status=IDENTITY_STATUS_BLOCKED,
                target_status=target_status,
                reason=(
                    "Transition is forbidden by the identity-state contract."
                ),
                errors=("current state must be RepositoryIdentityState",),
            )
        current_validation = validate_repository_identity_state(current)
        if not current_validation.valid:
            return IdentityTransitionValidation(
                allowed=False,
                current_status=current_status,
                target_status=target_status,
                reason=(
                    "Transition is forbidden by the identity-state contract."
                ),
                errors=(
                    "current state is invalid or blocked",
                    *current_validation.errors,
                ),
            )
        if not _same_physical_identity(current, target):
            errors.append(
                "repository_id, canonical_root, and storage_key are immutable"
            )
        if target.state_revision != current.state_revision + 1:
            if target.to_dict() != current.to_dict():
                errors.append(
                    "target state revision must increment by exactly one"
                )
        if (
            all(
                isinstance(warning, LegacyNamespaceWarning)
                for warning in current.legacy_namespace_warnings
            )
            and all(
                isinstance(warning, LegacyNamespaceWarning)
                for warning in target.legacy_namespace_warnings
            )
        ):
            target_warnings = {
                warning.namespace: warning
                for warning in target.legacy_namespace_warnings
            }
            if any(
                target_warnings.get(warning.namespace) != warning
                for warning in current.legacy_namespace_warnings
            ):
                errors.append(
                    "legacy namespace warnings cannot be removed or rewritten"
                )
        if target.archived_epochs[: len(current.archived_epochs)] != (
            current.archived_epochs
        ):
            errors.append("archived epoch history cannot be removed or rewritten")

        if current.to_dict() == target.to_dict():
            unique_errors = tuple(sorted(set(errors)))
            return IdentityTransitionValidation(
                allowed=not unique_errors,
                current_status=current_status,
                target_status=target_status,
                reason=(
                    "Identical valid state is an idempotent no-op."
                    if not unique_errors
                    else (
                        "Transition is forbidden by the identity-state "
                        "contract."
                    )
                ),
                errors=unique_errors,
            )

        warning_only_transition = (
            current_status
            in {
                IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED,
                IDENTITY_STATUS_CONFIRMED,
                IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED,
            }
            and target_status == current_status
            and len(target.legacy_namespace_warnings)
            > len(current.legacy_namespace_warnings)
            and target.state_revision == current.state_revision + 1
            and replace(
                target,
                legacy_namespace_warnings=(
                    current.legacy_namespace_warnings
                ),
                state_revision=current.state_revision,
            )
            == current
        )
        if warning_only_transition:
            unique_errors = tuple(sorted(set(errors)))
            return IdentityTransitionValidation(
                allowed=not unique_errors,
                current_status=current_status,
                target_status=target_status,
                reason=(
                    "Append-only legacy namespace warnings are allowed."
                    if not unique_errors
                    else (
                        "Transition is forbidden by the identity-state "
                        "contract."
                    )
                ),
                errors=unique_errors,
            )
        if (
            target.legacy_namespace_warnings
            != current.legacy_namespace_warnings
        ):
            errors.append(
                "legacy warnings may change only in a dedicated append-only "
                "transition"
            )

        if current_status in {
            IDENTITY_STATUS_ARCHIVED,
            IDENTITY_STATUS_BLOCKED,
        }:
            errors.append(f"{current_status} is terminal")
        elif (
            current_status
            == IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED
        ):
            if target_status != IDENTITY_STATUS_CONFIRMED:
                errors.append(
                    "initial confirmation may transition only to confirmed"
                )
            if target.confirmation.decision != DECISION_SAME_PROJECT:
                errors.append(
                    "initial confirmation requires an explicit same_project "
                    "human decision"
                )
            if (
                current.architecture_epoch != target.architecture_epoch
                or current.active_index_scope != target.active_index_scope
                or current.previous_index_scope
                != target.previous_index_scope
            ):
                errors.append(
                    "same_project must preserve the initial epoch and scope"
                )
            if (
                target.previous_project_tag
                != current.previous_project_tag
                or target.archived_epochs != current.archived_epochs
                or target.major_change != current.major_change
            ):
                errors.append(
                    "initial confirmation must preserve empty audit history"
                )
            if target.candidate_project_tag is not None:
                errors.append(
                    "confirmed state must clear the unconfirmed candidate tag"
                )
        elif current_status == IDENTITY_STATUS_CONFIRMED:
            if (
                target_status
                != IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED
            ):
                errors.append(
                    "confirmed may transition only to major-change review"
                )
            if not target.major_change.candidate:
                errors.append(
                    "major-change review requires a positive advisory candidate"
                )
            if (
                current.architecture_epoch != target.architecture_epoch
                or current.active_index_scope != target.active_index_scope
                or current.project_tag != target.project_tag
                or current.previous_project_tag
                != target.previous_project_tag
                or current.previous_index_scope
                != target.previous_index_scope
            ):
                errors.append(
                    "entering major-change review must preserve tag, epoch, "
                    "scope, and prior lineage"
                )
            if (
                target.confirmation != current.confirmation
                or target.archived_epochs != current.archived_epochs
                or target.candidate_project_tag
                != current.candidate_project_tag
            ):
                errors.append(
                    "entering major-change review must preserve confirmation "
                    "and prior audit history"
                )
        elif (
            current_status
            == IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED
        ):
            if target_status != IDENTITY_STATUS_CONFIRMED:
                errors.append(
                    "major-change review may unlock only a confirmed state"
                )
            expected_resolved_major = replace(
                current.major_change,
                candidate=False,
                resolved_at=target.confirmation.confirmed_at,
                resolution_decision=target.confirmation.decision,
            )
            if target.major_change != expected_resolved_major:
                errors.append(
                    "major-change resolution must preserve detection signals "
                    "and evidence and append only its resolution"
                )
            if target.confirmation == current.confirmation:
                errors.append(
                    "major-change resolution requires a fresh human "
                    "confirmation record"
                )
            if target.candidate_project_tag is not None:
                errors.append(
                    "major-change resolution must clear candidate_project_tag"
                )
            if target.confirmation.decision == DECISION_SAME_PROJECT:
                if (
                    current.architecture_epoch != target.architecture_epoch
                    or current.active_index_scope != target.active_index_scope
                    or current.previous_index_scope
                    != target.previous_index_scope
                ):
                    errors.append(
                        "same_project must preserve epoch and active scope"
                    )
                if target.archived_epochs != current.archived_epochs:
                    errors.append("same_project must not archive an epoch")
                expected_previous_tag = (
                    current.project_tag
                    if target.project_tag != current.project_tag
                    else current.previous_project_tag
                )
                if (
                    target.previous_project_tag
                    != expected_previous_tag
                ):
                    errors.append(
                        "same_project must preserve semantic tag lineage"
                    )
            elif (
                target.confirmation.decision
                == DECISION_NEW_ARCHITECTURE_EPOCH
            ):
                expected_epoch = (
                    1
                    if current.architecture_epoch is None
                    else current.architecture_epoch + 1
                )
                if target.architecture_epoch != expected_epoch:
                    errors.append(
                        "new architecture epoch must be the next explicit "
                        "integer increment"
                    )
                if target.active_index_scope == current.active_index_scope:
                    errors.append("new architecture epoch requires a new scope")
                if (
                    target.previous_index_scope
                    != current.active_index_scope
                    or target.previous_project_tag
                    != current.project_tag
                ):
                    errors.append(
                        "new architecture epoch must point to the immediately "
                        "previous scope and project tag"
                    )
                if len(target.archived_epochs) != (
                    len(current.archived_epochs) + 1
                ):
                    errors.append(
                        "new architecture epoch must append one archive record"
                    )
                else:
                    expected_archive = ArchivedEpochRecord(
                        identity_status=IDENTITY_STATUS_ARCHIVED,
                        architecture_epoch=current.architecture_epoch,
                        index_scope=current.active_index_scope,
                        project_tag=current.project_tag or "",
                        archived_at=(
                            target.confirmation.confirmed_at or ""
                        ),
                        archived_by=(
                            target.confirmation.confirmed_by or ""
                        ),
                        reason=target.confirmation.reason or "",
                    )
                    if target.archived_epochs[-1] != expected_archive:
                        errors.append(
                            "archive record must exactly preserve the previous "
                            "epoch and resolution audit"
                        )
            else:
                errors.append(
                    "major-change resolution requires same_project or "
                    "new_architecture_epoch"
                )
        elif current_status == IDENTITY_STATUS_UNINITIALIZED:
            errors.append("serialized uninitialized state is unsupported")
        else:
            errors.append(f"unknown current identity status: {current_status!r}")

    unique_errors = tuple(sorted(set(errors)))
    return IdentityTransitionValidation(
        allowed=not unique_errors,
        current_status=current_status,
        target_status=target_status,
        reason=(
            "Transition is allowed by the identity-state contract."
            if not unique_errors
            else "Transition is forbidden by the identity-state contract."
        ),
        errors=unique_errors,
    )


def validate_repository_identity_transition(
    current: RepositoryIdentityState | None,
    target: RepositoryIdentityState,
) -> IdentityTransitionValidation:
    """Compatibility alias for the stable transition validator."""
    return validate_identity_state_transition(current, target)


def _validate_confirmation_record(
    record: ConfirmationRecord,
) -> list[str]:
    errors: list[str] = []
    if record.decision is None:
        if any(
            value is not None
            for value in (
                record.confirmed_at,
                record.confirmed_by,
                record.reason,
            )
        ):
            errors.append("partial confirmation record is invalid")
        return errors
    if record.decision not in {
        DECISION_SAME_PROJECT,
        DECISION_NEW_ARCHITECTURE_EPOCH,
    }:
        errors.append("persisted confirmation decision does not unlock identity")
    try:
        timestamp = _normalize_timestamp(
            record.confirmed_at,
            field="confirmation.confirmed_at",
        )
        actor = _normalize_human_actor(record.confirmed_by)
        reason = _normalize_safe_text(
            record.reason,
            field="confirmation.reason",
            maximum=MAX_REASON_LENGTH,
        )
        if (
            timestamp != record.confirmed_at
            or actor != record.confirmed_by
            or reason != record.reason
        ):
            errors.append(
                "confirmation audit fields must use their canonical text"
            )
    except IdentityStateError as exc:
        errors.append(str(exc))
    return errors


def _validate_repository_identity_state_impl(
    state: RepositoryIdentityState,
    *,
    expected_identity: RepositoryIdentity | None = None,
) -> IdentityStateValidation:
    """Validate structural, identity, epoch, and permission invariants."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(state, RepositoryIdentityState):
        return IdentityStateValidation(
            False,
            IDENTITY_STATUS_BLOCKED,
            ("state must be RepositoryIdentityState",),
        )
    if not isinstance(state.confirmation, ConfirmationRecord):
        errors.append("confirmation must be a ConfirmationRecord")
        state = replace(state, confirmation=ConfirmationRecord())
    if not isinstance(state.major_change, MajorChangeRecord):
        errors.append("major_change must be a MajorChangeRecord")
        state = replace(state, major_change=MajorChangeRecord())
    if not isinstance(state.permissions, CanonicalIdentityPermissions):
        errors.append("permissions must be CanonicalIdentityPermissions")
        state = replace(state, permissions=_all_false_permissions())
    if not isinstance(
        state.activation_graph_independence,
        ActivationGraphIndependence,
    ):
        errors.append(
            "activation_graph_independence must be its canonical record"
        )
        state = replace(
            state,
            activation_graph_independence=(
                activation_graph_identity_independence_metadata()
            ),
        )
    if not isinstance(state.archived_epochs, tuple):
        errors.append("archived_epochs must be an immutable tuple")
        state = replace(state, archived_epochs=())
    if not isinstance(state.legacy_namespace_warnings, tuple):
        errors.append(
            "legacy_namespace_warnings must be an immutable tuple"
        )
        state = replace(state, legacy_namespace_warnings=())
    if not isinstance(state.state_errors, tuple):
        errors.append("state_errors must be an immutable tuple")
        state = replace(state, state_errors=())

    if (
        type(state.schema_version) is not int
        or state.schema_version != SCHEMA_VERSION
    ):
        errors.append(
            f"unsupported schema_version: {state.schema_version!r}"
        )
    if state.artifact_kind != ARTIFACT_KIND:
        errors.append(f"unexpected artifact_kind: {state.artifact_kind!r}")
    if not is_repository_id(state.repository_id):
        errors.append("repository_id is malformed")
    else:
        try:
            if state.repository_id != (
                derive_repository_id_from_canonical_root(
                    state.canonical_root
                )
            ):
                errors.append(
                    "repository_id does not match canonical_root"
                )
            if state.storage_key != derive_repository_storage_key_from_id(
                state.repository_id
            ):
                errors.append(
                    "storage_key does not match the canonical repository_id"
                )
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
    if (
        not isinstance(state.storage_key, str)
        or _SAFE_STORAGE_SEGMENT_RE.fullmatch(state.storage_key) is None
        or len(state.storage_key) > 128
    ):
        errors.append("storage_key is not one bounded safe path segment")
    if (
        not isinstance(state.canonical_root, str)
        or not state.canonical_root.strip()
        or not Path(state.canonical_root).is_absolute()
    ):
        errors.append("canonical_root must be a nonblank absolute path")
    if state.identity_status not in IDENTITY_STATUSES:
        errors.append(
            f"unknown identity_status: {state.identity_status!r}"
        )
    try:
        epoch = _normalize_epoch(
            state.architecture_epoch,
            field="architecture_epoch",
            allow_baseline=True,
        )
        expected_scope = derive_repository_index_scope_from_id(
            state.repository_id,
            architecture_epoch=epoch,
        )
        if state.active_index_scope != expected_scope:
            errors.append(
                "active_index_scope does not match repository_id and epoch"
            )
    except (IdentityStateError, ValueError) as exc:
        errors.append(str(exc))
    if not is_code_index_scope(state.active_index_scope):
        errors.append("active_index_scope is not a strict code-index scope")
    if state.previous_index_scope is not None:
        if not is_code_index_scope(state.previous_index_scope):
            errors.append("previous_index_scope is malformed")
        elif state.previous_index_scope == state.active_index_scope:
            errors.append(
                "previous_index_scope must differ from active_index_scope"
            )
    if (
        isinstance(state.state_revision, bool)
        or not isinstance(state.state_revision, int)
        or state.state_revision < 0
    ):
        errors.append("state_revision must be a non-negative integer")
    if type(state.human_confirmation_required) is not bool:
        errors.append("human_confirmation_required must be boolean")
    for field, value in (
        ("project_tag", state.project_tag),
        ("previous_project_tag", state.previous_project_tag),
        ("candidate_project_tag", state.candidate_project_tag),
    ):
        try:
            normalized_tag = _normalize_project_tag(
                value,
                field=field,
                allow_none=True,
            )
            if normalized_tag != value:
                errors.append(
                    f"{field} must use its canonical trimmed value"
                )
        except IdentityStateError as exc:
            errors.append(str(exc))

    errors.extend(_validate_confirmation_record(state.confirmation))
    if state.identity_status == IDENTITY_STATUS_UNINITIALIZED:
        if state.state_revision != 0:
            errors.append("uninitialized in-memory state revision must be 0")
        if state.project_tag is not None:
            errors.append("uninitialized state cannot have a confirmed tag")
    elif (
        state.identity_status
        == IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED
    ):
        if state.state_revision < 1:
            errors.append(
                "initial confirmation state revision must be at least 1"
            )
        if state.architecture_epoch is not None:
            errors.append(
                "initial confirmation must use the compatibility baseline"
            )
        if (
            state.previous_index_scope is not None
            or state.archived_epochs
            or state.major_change != MajorChangeRecord()
        ):
            errors.append(
                "initial confirmation cannot contain epoch or major-change "
                "history"
            )
        if state.project_tag is not None:
            errors.append(
                "initial confirmation state must have project_tag=None"
            )
        if state.human_confirmation_required is not True:
            errors.append(
                "initial confirmation state must require a human decision"
            )
        if state.confirmation.decision is not None:
            errors.append(
                "initial confirmation state cannot contain confirmation"
            )
    elif state.identity_status == IDENTITY_STATUS_CONFIRMED:
        if state.project_tag is None:
            errors.append("confirmed state requires a semantic project tag")
        if state.human_confirmation_required is not False:
            errors.append("confirmed state cannot require confirmation")
        if state.confirmation.decision not in {
            DECISION_SAME_PROJECT,
            DECISION_NEW_ARCHITECTURE_EPOCH,
        }:
            errors.append(
                "confirmed state requires an applied human decision"
            )
        if state.major_change.candidate:
            errors.append(
                "confirmed state cannot retain an unresolved major candidate"
            )
        if state.candidate_project_tag is not None:
            errors.append(
                "confirmed state cannot retain an unconfirmed candidate tag"
            )
    elif (
        state.identity_status
        == IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED
    ):
        if state.project_tag is None:
            errors.append(
                "major-change review must preserve the confirmed project tag"
            )
        if state.human_confirmation_required is not True:
            errors.append(
                "major-change review must require human confirmation"
            )
        if not state.major_change.candidate:
            errors.append(
                "major-change review requires candidate=true"
            )
        if state.candidate_project_tag is not None:
            errors.append(
                "major-change review cannot retain an unconfirmed candidate "
                "tag"
            )
        if state.confirmation.decision not in {
            DECISION_SAME_PROJECT,
            DECISION_NEW_ARCHITECTURE_EPOCH,
        }:
            errors.append(
                "major-change review requires the prior confirmed identity "
                "audit"
            )
        if (
            state.major_change.resolved_at is not None
            or state.major_change.resolution_decision is not None
        ):
            errors.append(
                "pending major-change review cannot already be resolved"
            )
    elif state.identity_status in {
        IDENTITY_STATUS_ARCHIVED,
        IDENTITY_STATUS_BLOCKED,
    }:
        if state.human_confirmation_required is not (
            state.identity_status == IDENTITY_STATUS_BLOCKED
        ):
            errors.append(
                f"{state.identity_status} has contradictory confirmation flag"
            )

    if type(state.major_change.candidate) is not bool:
        errors.append("major_change.candidate must be boolean")
    if state.major_change.detected_at is not None:
        try:
            normalized_detected_at = _normalize_timestamp(
                state.major_change.detected_at,
                field="major_change.detected_at",
            )
            if normalized_detected_at != state.major_change.detected_at:
                errors.append(
                    "major_change.detected_at must use canonical text"
                )
        except IdentityStateError as exc:
            errors.append(str(exc))
    major_history_present = (
        state.major_change.detected_at is not None
        or bool(state.major_change.signals)
        or bool(state.major_change.evidence)
    )
    epoch_count = (
        state.architecture_epoch
        if type(state.architecture_epoch) is int
        and 0 < state.architecture_epoch <= MAX_ARCHITECTURE_EPOCH
        else 0
    )
    if state.identity_status == IDENTITY_STATUS_CONFIRMED:
        minimum_revision = 2 + (2 * epoch_count)
        if (
            major_history_present
            and state.major_change.resolution_decision
            == DECISION_SAME_PROJECT
        ):
            minimum_revision += 2
        if state.state_revision < minimum_revision:
            errors.append(
                f"confirmed state revision must be at least "
                f"{minimum_revision} for its decision history"
            )
    elif (
        state.identity_status
        == IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED
    ):
        minimum_revision = 3 + (2 * epoch_count)
        if state.state_revision < minimum_revision:
            errors.append(
                "major-change review revision is too small for its "
                "decision history"
            )
    if (
        state.identity_status == IDENTITY_STATUS_CONFIRMED
        and state.confirmation.decision
        == DECISION_NEW_ARCHITECTURE_EPOCH
        and state.architecture_epoch is None
    ):
        errors.append(
            "new_architecture_epoch confirmation requires an explicit epoch"
        )
    if (
        state.architecture_epoch is not None
        and state.identity_status
        in {
            IDENTITY_STATUS_CONFIRMED,
            IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED,
        }
        and not major_history_present
    ):
        errors.append(
            "explicit architecture epoch requires preserved major-change "
            "decision history"
        )
    if state.major_change.candidate:
        if state.major_change.detected_at is None:
            errors.append(
                "major-change candidate requires a detection timestamp"
            )
        if not state.major_change.signals:
            errors.append(
                "major-change candidate requires at least one signal"
            )
        if (
            state.major_change.resolved_at is not None
            or state.major_change.resolution_decision is not None
        ):
            errors.append(
                "major-change candidate cannot already contain a resolution"
            )
    elif major_history_present:
        if state.major_change.detected_at is None:
            errors.append(
                "resolved major-change history requires a detection timestamp"
            )
        if not state.major_change.signals:
            errors.append(
                "resolved major-change history requires at least one signal"
            )
        if (
            state.major_change.resolved_at is None
            or state.major_change.resolution_decision is None
        ):
            errors.append(
                "resolved major-change history requires both resolution fields"
            )
    elif (
        state.major_change.resolved_at is not None
        or state.major_change.resolution_decision is not None
    ):
        errors.append(
            "major-change resolution requires preserved detection history"
        )
    if (
        not isinstance(state.major_change.signals, tuple)
        or not all(
            isinstance(signal, str)
            for signal in state.major_change.signals
        )
        or tuple(sorted(set(state.major_change.signals)))
        != state.major_change.signals
        or len(state.major_change.signals) > MAX_SIGNAL_COUNT
        or any(
            signal not in MAJOR_CHANGE_SIGNAL_IDS
            for signal in state.major_change.signals
        )
    ):
        errors.append(
            "major_change.signals must be bounded, unique, sorted, and known"
        )
    try:
        if _normalize_evidence(state.major_change.evidence) != (
            state.major_change.evidence
        ):
            errors.append(
                "major_change.evidence must be unique and sorted"
            )
    except IdentityStateError as exc:
        errors.append(str(exc))
    if state.major_change.resolution_decision is None:
        if state.major_change.resolved_at is not None:
            errors.append(
                "major_change.resolved_at requires a resolution decision"
            )
    else:
        if (
            not isinstance(
                state.major_change.resolution_decision,
                str,
            )
            or state.major_change.resolution_decision not in {
                DECISION_SAME_PROJECT,
                DECISION_NEW_ARCHITECTURE_EPOCH,
            }
        ):
            errors.append("major_change resolution decision is invalid")
        try:
            normalized_resolved_at = _normalize_timestamp(
                state.major_change.resolved_at,
                field="major_change.resolved_at",
            )
            if normalized_resolved_at != state.major_change.resolved_at:
                errors.append(
                    "major_change.resolved_at must use canonical text"
                )
        except IdentityStateError as exc:
            errors.append(str(exc))
    if (
        state.identity_status == IDENTITY_STATUS_CONFIRMED
        and major_history_present
        and (
            state.major_change.resolution_decision
            != state.confirmation.decision
            or state.major_change.resolved_at
            != state.confirmation.confirmed_at
        )
    ):
        errors.append(
            "resolved major-change audit must match the fresh confirmation"
        )
    if (
        state.major_change.detected_at is not None
        and state.major_change.candidate
        and state.confirmation.confirmed_at is not None
    ):
        try:
            if _timestamp_instant(
                state.major_change.detected_at,
                field="major_change.detected_at",
            ) < _timestamp_instant(
                state.confirmation.confirmed_at,
                field="confirmation.confirmed_at",
            ):
                errors.append(
                    "major-change detection cannot predate the confirmed "
                    "identity it reviews"
                )
        except IdentityStateError:
            pass
    if (
        state.major_change.detected_at is not None
        and state.major_change.resolved_at is not None
    ):
        try:
            if _timestamp_instant(
                state.major_change.resolved_at,
                field="major_change.resolved_at",
            ) < _timestamp_instant(
                state.major_change.detected_at,
                field="major_change.detected_at",
            ):
                errors.append(
                    "major-change resolution cannot predate its detection"
                )
        except IdentityStateError:
            pass

    archived_scopes: set[str] = set()
    archived_epochs: set[int | None] = set()
    for index, archived in enumerate(state.archived_epochs):
        prefix = f"archived_epochs[{index}]"
        if not isinstance(archived, ArchivedEpochRecord):
            errors.append(f"{prefix} is malformed")
            continue
        if archived.identity_status != IDENTITY_STATUS_ARCHIVED:
            errors.append(f"{prefix} must have archived status")
        try:
            archived_epoch = _normalize_epoch(
                archived.architecture_epoch,
                field=f"{prefix}.architecture_epoch",
                allow_baseline=True,
            )
            expected_archived_scope = (
                derive_repository_index_scope_from_id(
                    state.repository_id,
                    architecture_epoch=archived_epoch,
                )
            )
            if archived.index_scope != expected_archived_scope:
                errors.append(
                    f"{prefix}.index_scope does not match its epoch"
                )
        except (IdentityStateError, ValueError) as exc:
            errors.append(str(exc))
        try:
            archived_tag = _normalize_project_tag(
                archived.project_tag,
                field=f"{prefix}.project_tag",
                allow_none=False,
            )
            archived_at = _normalize_timestamp(
                archived.archived_at,
                field=f"{prefix}.archived_at",
            )
            archived_by = _normalize_human_actor(archived.archived_by)
            archived_reason = _normalize_safe_text(
                archived.reason,
                field=f"{prefix}.reason",
                maximum=MAX_REASON_LENGTH,
            )
            if (
                archived_tag != archived.project_tag
                or archived_at != archived.archived_at
                or archived_by != archived.archived_by
                or archived_reason != archived.reason
            ):
                errors.append(
                    f"{prefix} audit fields must use canonical text"
                )
        except IdentityStateError as exc:
            errors.append(str(exc))
        if (
            archived.readable is not True
            or archived.writes_allowed is not False
            or archived.reconciliation_allowed is not False
            or archived.deleted is not False
        ):
            errors.append(
                f"{prefix} must remain readable, history-only, and preserved"
            )
        if archived.index_scope in archived_scopes:
            errors.append("archived index scopes must be unique")
        archived_scopes.add(archived.index_scope)
        if archived.architecture_epoch in archived_epochs:
            errors.append("archived architecture epochs must be unique")
        archived_epochs.add(archived.architecture_epoch)
    if state.active_index_scope in archived_scopes:
        errors.append("active index scope cannot also be archived")
    if (
        state.previous_index_scope is not None
        and state.previous_index_scope not in archived_scopes
    ):
        errors.append(
            "previous_index_scope must be retained in archived epoch history"
        )
    if state.architecture_epoch is None:
        if state.archived_epochs:
            errors.append(
                "compatibility baseline cannot have archived epoch history"
            )
        if state.previous_index_scope is not None:
            errors.append(
                "compatibility baseline cannot have a previous index scope"
            )
    elif type(state.architecture_epoch) is int:
        lineage_matches = (
            len(state.archived_epochs) == state.architecture_epoch
        )
        if lineage_matches:
            for index, record in enumerate(state.archived_epochs):
                expected_epoch = None if index == 0 else index
                if (
                    not isinstance(record, ArchivedEpochRecord)
                    or record.architecture_epoch != expected_epoch
                ):
                    lineage_matches = False
                    break
        if not lineage_matches:
            errors.append(
                "architecture epoch history must preserve the baseline and "
                "every prior integer epoch in order"
            )
        if (
            not state.archived_epochs
            or state.previous_index_scope
            != state.archived_epochs[-1].index_scope
        ):
            errors.append(
                "active architecture epoch must point to the immediately "
                "previous archived scope"
            )

    if (
        len(state.legacy_namespace_warnings)
        > MAX_LEGACY_NAMESPACE_COUNT
    ):
        errors.append(
            "legacy namespace warnings exceed the bounded item count"
        )
    seen_legacy: set[str] = set()
    for index, warning in enumerate(state.legacy_namespace_warnings):
        prefix = f"legacy_namespace_warnings[{index}]"
        if not isinstance(warning, LegacyNamespaceWarning):
            errors.append(f"{prefix} is malformed")
            continue
        try:
            normalized_namespace = _normalize_safe_text(
                warning.namespace,
                field=f"{prefix}.namespace",
                maximum=MAX_LEGACY_NAMESPACE_LENGTH,
            )
            if normalized_namespace != warning.namespace:
                errors.append(
                    f"{prefix}.namespace must use canonical text"
                )
        except IdentityStateError as exc:
            errors.append(str(exc))
        if warning.namespace in seen_legacy:
            errors.append("legacy namespace warnings must be unique")
        seen_legacy.add(warning.namespace)
        if (
            warning.warning != LEGACY_NAMESPACE_WARNING_TEXT
            or warning.preserve is not True
            or warning.deletion_allowed is not False
            or warning.automatic_epoch_binding_allowed is not False
            or warning.recommended_phase != LEGACY_MIGRATION_PHASE
        ):
            errors.append(
                f"{prefix} must preserve and defer legacy namespace handling"
            )
    warning_names = tuple(
        warning.namespace
        for warning in state.legacy_namespace_warnings
        if isinstance(warning, LegacyNamespaceWarning)
    )
    if (
        len(warning_names) != len(state.legacy_namespace_warnings)
        or tuple(sorted(seen_legacy)) != warning_names
    ):
        errors.append("legacy namespace warnings must be sorted")

    expected_permissions = _abstract_permissions_for_status(
        state.identity_status
    )
    if any(
        type(value) is not bool
        for value in state.permissions.to_dict().values()
    ):
        errors.append("all persisted permission fields must be booleans")
    if state.permissions != expected_permissions:
        errors.append(
            "persisted permissions contradict the derived identity matrix"
        )
    if state.permissions.trusted_current_claim_allowed:
        errors.append(
            "INDEX.1D.2B cannot permit a trusted-current claim"
        )
    if state.permission_layer != PERMISSION_LAYER:
        errors.append("permission_layer must remain identity_only")
    if state.trusted_completion_required is not True:
        errors.append("trusted completion must remain separately required")
    if state.trusted_completion_phase != TRUSTED_COMPLETION_PHASE:
        errors.append("trusted completion must remain deferred to INDEX.1D.2C")
    if (
        state.activation_graph_independence
        != activation_graph_identity_independence_metadata()
    ):
        errors.append("Activation Graph independence metadata was altered")
    activation = state.activation_graph_independence
    if any(
        type(value) is not bool
        for value in (
            activation.operation_allowed,
            activation.may_confirm_project,
            activation.may_create_architecture_epoch,
            activation.may_advance_canonical_manifest,
            activation.may_reconcile_canonical_rows,
            activation.may_change_project_tag,
        )
    ):
        errors.append(
            "all Activation Graph independence flags must be booleans"
        )
    if (
        not all(isinstance(error, str) for error in state.state_errors)
        or tuple(sorted(set(state.state_errors))) != state.state_errors
    ):
        errors.append("state_errors must be unique sorted text")
    if state.identity_status not in {
        IDENTITY_STATUS_BLOCKED,
    } and state.state_errors:
        errors.append("valid non-blocked state cannot contain state_errors")

    if expected_identity is not None:
        if state.repository_id != expected_identity.repository_id:
            errors.append("state repository_id does not match the repository")
        if state.canonical_root != expected_identity.canonical_root:
            errors.append("state canonical_root does not match the repository")
        if state.storage_key != expected_identity.storage_key:
            errors.append("state storage_key does not match the repository")

    unique_errors = tuple(sorted(set(errors)))
    effective_status = (
        state.identity_status
        if not unique_errors
        else IDENTITY_STATUS_BLOCKED
    )
    return IdentityStateValidation(
        valid=not unique_errors,
        effective_status=effective_status,
        errors=unique_errors,
        warnings=tuple(sorted(set(warnings))),
    )


def validate_repository_identity_state(
    state: RepositoryIdentityState,
    *,
    expected_identity: RepositoryIdentity | None = None,
) -> IdentityStateValidation:
    """Validate any caller-supplied typed state and fail closed, never open."""
    try:
        return _validate_repository_identity_state_impl(
            state,
            expected_identity=expected_identity,
        )
    except Exception as exc:
        return IdentityStateValidation(
            valid=False,
            effective_status=IDENTITY_STATUS_BLOCKED,
            errors=(
                "identity-state validation failed closed "
                f"({type(exc).__name__})",
            ),
        )


_TOP_LEVEL_KEYS = frozenset(
    RepositoryIdentityState.__dataclass_fields__.keys()
)
_CONFIRMATION_KEYS = frozenset(
    ConfirmationRecord.__dataclass_fields__.keys()
)
_MAJOR_CHANGE_KEYS = frozenset(
    MajorChangeRecord.__dataclass_fields__.keys()
)
_ARCHIVED_EPOCH_KEYS = frozenset(
    ArchivedEpochRecord.__dataclass_fields__.keys()
)
_LEGACY_WARNING_KEYS = frozenset(
    LegacyNamespaceWarning.__dataclass_fields__.keys()
)
_PERMISSION_KEYS = frozenset(
    CanonicalIdentityPermissions.__dataclass_fields__.keys()
)
_ACTIVATION_KEYS = frozenset(
    ActivationGraphIndependence.__dataclass_fields__.keys()
)


def _require_exact_keys(
    value: Any,
    expected: frozenset[str],
    *,
    field: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IdentityStateError(f"{field} must be a JSON object")
    keys = set(value)
    missing = expected - keys
    unknown = keys - expected
    if missing:
        raise IdentityStateError(
            f"{field} is missing fields: "
            + ", ".join(sorted(missing))
        )
    if unknown:
        raise IdentityStateError(
            f"{field} has unsupported fields: "
            + ", ".join(sorted(str(key) for key in unknown))
        )
    return value


def _require_json_list(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise IdentityStateError(f"{field} must be a JSON array")
    return value


def _contains_secret_field(value: Any) -> bool:
    pending = [value]
    visited = 0
    while pending:
        current = pending.pop()
        visited += 1
        if visited > 10_000:
            raise IdentityStateError(
                "identity-state JSON structure exceeds the node bound"
            )
        if isinstance(current, Mapping):
            for key, item in current.items():
                if _SECRET_FIELD_RE.search(str(key)) is not None:
                    return True
                pending.append(item)
        elif isinstance(current, list):
            pending.extend(current)
    return False


def _state_from_mapping(value: Mapping[str, Any]) -> RepositoryIdentityState:
    data = _require_exact_keys(
        value,
        _TOP_LEVEL_KEYS,
        field="identity_state",
    )
    if _contains_secret_field(data):
        raise IdentityStateError(
            "identity state contains a secret-shaped field"
        )
    confirmation_data = _require_exact_keys(
        data["confirmation"],
        _CONFIRMATION_KEYS,
        field="confirmation",
    )
    major_data = _require_exact_keys(
        data["major_change"],
        _MAJOR_CHANGE_KEYS,
        field="major_change",
    )
    permission_data = _require_exact_keys(
        data["permissions"],
        _PERMISSION_KEYS,
        field="permissions",
    )
    activation_data = _require_exact_keys(
        data["activation_graph_independence"],
        _ACTIVATION_KEYS,
        field="activation_graph_independence",
    )
    archived_records: list[ArchivedEpochRecord] = []
    for index, item in enumerate(
        _require_json_list(
            data["archived_epochs"],
            field="archived_epochs",
        )
    ):
        record = _require_exact_keys(
            item,
            _ARCHIVED_EPOCH_KEYS,
            field=f"archived_epochs[{index}]",
        )
        archived_records.append(ArchivedEpochRecord(**dict(record)))
    legacy_warnings: list[LegacyNamespaceWarning] = []
    for index, item in enumerate(
        _require_json_list(
            data["legacy_namespace_warnings"],
            field="legacy_namespace_warnings",
        )
    ):
        record = _require_exact_keys(
            item,
            _LEGACY_WARNING_KEYS,
            field=f"legacy_namespace_warnings[{index}]",
        )
        legacy_warnings.append(LegacyNamespaceWarning(**dict(record)))

    major_values = dict(major_data)
    major_values["signals"] = tuple(
        _require_json_list(
            major_values["signals"],
            field="major_change.signals",
        )
    )
    major_values["evidence"] = tuple(
        _require_json_list(
            major_values["evidence"],
            field="major_change.evidence",
        )
    )
    activation_values = dict(activation_data)
    activation_values["allowed_identity_statuses"] = tuple(
        _require_json_list(
            activation_values["allowed_identity_statuses"],
            field=(
                "activation_graph_independence."
                "allowed_identity_statuses"
            ),
        )
    )
    state_errors = tuple(
        _require_json_list(
            data["state_errors"],
            field="state_errors",
        )
    )
    return RepositoryIdentityState(
        schema_version=data["schema_version"],
        artifact_kind=data["artifact_kind"],
        repository_id=data["repository_id"],
        canonical_root=data["canonical_root"],
        storage_key=data["storage_key"],
        identity_status=data["identity_status"],
        project_tag=data["project_tag"],
        previous_project_tag=data["previous_project_tag"],
        candidate_project_tag=data["candidate_project_tag"],
        architecture_epoch=data["architecture_epoch"],
        active_index_scope=data["active_index_scope"],
        previous_index_scope=data["previous_index_scope"],
        human_confirmation_required=data[
            "human_confirmation_required"
        ],
        confirmation=ConfirmationRecord(**dict(confirmation_data)),
        major_change=MajorChangeRecord(**major_values),
        archived_epochs=tuple(archived_records),
        legacy_namespace_warnings=tuple(legacy_warnings),
        permissions=CanonicalIdentityPermissions(**dict(permission_data)),
        activation_graph_independence=ActivationGraphIndependence(
            **activation_values
        ),
        permission_layer=data["permission_layer"],
        trusted_completion_required=data[
            "trusted_completion_required"
        ],
        trusted_completion_phase=data["trusted_completion_phase"],
        state_revision=data["state_revision"],
        state_errors=state_errors,
    )


def _strict_object_pairs(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IdentityStateError(
                f"duplicate JSON object key: {key!r}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise IdentityStateError(
        f"non-standard JSON numeric constant is forbidden: {value}"
    )


def _blocked_state(
    identity: RepositoryIdentity,
    errors: Sequence[str],
) -> RepositoryIdentityState:
    normalized_errors = tuple(sorted(set(str(error) for error in errors)))
    return _base_state(
        identity,
        status=IDENTITY_STATUS_BLOCKED,
        architecture_epoch=None,
        revision=0,
        state_errors=normalized_errors,
    )


def parse_repository_identity_state(
    payload: bytes,
    *,
    expected_identity: RepositoryIdentity,
    path: str = "",
) -> IdentityStateLoadResult:
    """Strictly parse bytes; malformed content becomes an explicit blocked view."""
    errors: list[str] = []
    if not isinstance(payload, bytes):
        errors.append("identity-state payload must be bytes")
    elif len(payload) > MAX_IDENTITY_STATE_BYTES:
        errors.append(
            f"identity-state payload exceeds {MAX_IDENTITY_STATE_BYTES} bytes"
        )
    else:
        try:
            text = payload.decode("utf-8", errors="strict")
            raw = json.loads(
                text,
                object_pairs_hook=_strict_object_pairs,
                parse_constant=_reject_json_constant,
            )
            if not isinstance(raw, Mapping):
                raise IdentityStateError(
                    "identity-state JSON root must be an object"
                )
            state = _state_from_mapping(raw)
            validation = validate_repository_identity_state(
                state,
                expected_identity=expected_identity,
            )
            if validation.valid:
                if state.identity_status in {
                    IDENTITY_STATUS_UNINITIALIZED,
                    IDENTITY_STATUS_BLOCKED,
                }:
                    raise IdentityStateError(
                        f"persisted {state.identity_status} state is not an "
                        "operable identity artifact"
                    )
                return IdentityStateLoadResult(
                    exists=True,
                    valid=True,
                    status=state.identity_status,
                    path=path,
                    state=state,
                    warnings=validation.warnings,
                )
            errors.extend(validation.errors)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            IdentityStateError,
            RecursionError,
            TypeError,
            ValueError,
        ) as exc:
            errors.append(str(exc))
    blocked = _blocked_state(expected_identity, errors)
    return IdentityStateLoadResult(
        exists=True,
        valid=False,
        status=IDENTITY_STATUS_BLOCKED,
        path=path,
        state=blocked,
        errors=tuple(sorted(set(errors))),
    )


def serialize_repository_identity_state(
    state: RepositoryIdentityState,
) -> bytes:
    """Serialize one valid persistable state deterministically."""
    validation = validate_repository_identity_state(state)
    errors = list(validation.errors)
    if state.identity_status in {
        IDENTITY_STATUS_UNINITIALIZED,
        IDENTITY_STATUS_BLOCKED,
    }:
        errors.append(
            f"{state.identity_status} is not a persistable identity state"
        )
    if errors:
        raise IdentityStateError("; ".join(sorted(set(errors))))
    text = json.dumps(
        state.to_dict(),
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
    )
    payload = (text + "\n").encode("utf-8")
    if len(payload) > MAX_IDENTITY_STATE_BYTES:
        raise IdentityStateError(
            f"serialized identity state exceeds {MAX_IDENTITY_STATE_BYTES} bytes"
        )
    return payload


def render_repository_identity_state_json(
    state: RepositoryIdentityState,
) -> str:
    """Return the deterministic UTF-8 JSON representation as text."""
    return serialize_repository_identity_state(state).decode("utf-8")


def _is_reparse_point(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except (
        OSError,
        IdentityStateError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        raise IdentityStateStorageError(
            f"cannot inspect state path component: {path}"
        ) from exc
    if stat.S_ISLNK(metadata.st_mode):
        return True
    junction_check = getattr(path, "is_junction", None)
    if callable(junction_check):
        try:
            if junction_check():
                return True
        except OSError as exc:
            raise IdentityStateStorageError(
                f"cannot inspect junction state: {path}"
            ) from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(reparse_flag and file_attributes & reparse_flag)


def _assert_safe_artifact_path(
    root: Path,
    path: Path,
    *,
    filename: str,
) -> None:
    root_absolute = root.expanduser().absolute()
    for ancestor in reversed(root_absolute.parents):
        if _is_reparse_point(ancestor):
            raise IdentityStateStorageError(
                "symlink, junction, or reparse root ancestor is forbidden: "
                f"{ancestor}"
            )
    try:
        relative = path.absolute().relative_to(root_absolute)
    except ValueError as exc:
        raise IdentityStateStorageError(
            "identity-state path escapes repository-intelligence root"
        ) from exc
    if relative.parts != (path.parent.name, filename):
        raise IdentityStateStorageError(
            "identity-state artifact path has unexpected components"
        )
    for component in (root_absolute, path.parent, path):
        if _is_reparse_point(component):
            raise IdentityStateStorageError(
                f"symlink, junction, or reparse state path is forbidden: "
                f"{component}"
            )
    if root_absolute.exists() and not root_absolute.is_dir():
        raise IdentityStateStorageError(
            "repository-intelligence root is not a directory"
        )
    if path.parent.exists() and not path.parent.is_dir():
        raise IdentityStateStorageError(
            "repository identity namespace is not a directory"
        )
    if path.exists() and not path.is_file():
        raise IdentityStateStorageError(
            "identity-state artifact is not a regular file"
        )
    resolved_root = str(root_absolute.resolve(strict=False))
    resolved_parent = str(path.parent.resolve(strict=False))
    if os.name == "nt":
        if resolved_root.startswith("\\\\?\\UNC\\"):
            resolved_root = "\\\\" + resolved_root[8:]
        elif resolved_root.startswith("\\\\?\\"):
            resolved_root = resolved_root[4:]
        if resolved_parent.startswith("\\\\?\\UNC\\"):
            resolved_parent = "\\\\" + resolved_parent[8:]
        elif resolved_parent.startswith("\\\\?\\"):
            resolved_parent = resolved_parent[4:]
    resolved_root = os.path.normpath(resolved_root)
    resolved_parent = os.path.normpath(resolved_parent)
    try:
        common = os.path.commonpath(
            (resolved_root, resolved_parent)
        )
    except ValueError as exc:
        raise IdentityStateStorageError(
            "identity-state root and target are on incompatible paths"
        ) from exc
    if os.path.normcase(common) != os.path.normcase(resolved_root):
        raise IdentityStateStorageError(
            "resolved identity-state path escapes repository-intelligence root"
        )


def _assert_safe_state_path(root: Path, path: Path) -> None:
    _assert_safe_artifact_path(
        root,
        path,
        filename=IDENTITY_STATE_FILENAME,
    )


def _assert_safe_lock_path(root: Path, path: Path) -> None:
    _assert_safe_artifact_path(
        root,
        path,
        filename=IDENTITY_STATE_LOCK_FILENAME,
    )
    if path.exists():
        try:
            metadata = path.lstat()
        except (OSError, TypeError, ValueError) as exc:
            raise IdentityStateStorageError(
                "cannot inspect repository identity-state lock"
            ) from exc
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size != 0
        ):
            raise IdentityStateStorageError(
                "identity-state lock must be one contained zero-content "
                "regular file without hard links"
            )


def _assert_open_artifact_identity(
    handle: Any,
    path: Path,
    *,
    label: str,
    require_empty: bool,
) -> None:
    descriptor_metadata = os.fstat(handle.fileno())
    path_metadata = os.stat(path, follow_symlinks=False)
    if (
        not stat.S_ISREG(descriptor_metadata.st_mode)
        or descriptor_metadata.st_nlink != 1
        or (require_empty and descriptor_metadata.st_size != 0)
        or (
            descriptor_metadata.st_dev,
            descriptor_metadata.st_ino,
        )
        != (path_metadata.st_dev, path_metadata.st_ino)
    ):
        content = " zero-content" if require_empty else ""
        raise IdentityStateStorageError(
            f"opened {label} is not the contained single-link{content} "
            "regular artifact"
        )


def get_repository_identity_state_path(
    identity_or_repo: RepositoryIdentity | str | os.PathLike[str],
    *,
    repository_intelligence_root: str | os.PathLike[str] | None = None,
) -> Path:
    """Return the fixed state path without creating directories."""
    identity = _coerce_identity(identity_or_repo)
    expected_storage_key = derive_repository_storage_key_from_id(
        identity.repository_id
    )
    if identity.storage_key != expected_storage_key:
        raise IdentityStateStorageError(
            "identity storage_key does not match repository_id"
        )
    if (
        _SAFE_STORAGE_SEGMENT_RE.fullmatch(identity.storage_key) is None
        or len(identity.storage_key) > 128
    ):
        raise IdentityStateStorageError(
            "identity storage_key is not a bounded safe path segment"
        )
    root = Path(
        repository_intelligence_root
        if repository_intelligence_root is not None
        else DEFAULT_REPOSITORY_INTELLIGENCE_ROOT
    ).expanduser().absolute()
    path = root / identity.storage_key / IDENTITY_STATE_FILENAME
    _assert_safe_state_path(root, path)
    return path


def repository_identity_state_path(
    repository_intelligence_root: str | os.PathLike[str],
    identity_or_repo: RepositoryIdentity | str | os.PathLike[str],
) -> Path:
    """Positional-root compatibility wrapper for storage integrations."""
    return get_repository_identity_state_path(
        identity_or_repo,
        repository_intelligence_root=repository_intelligence_root,
    )


def load_repository_identity_state(
    identity_or_repo: RepositoryIdentity | str | os.PathLike[str],
    *,
    repository_intelligence_root: str | os.PathLike[str] | None = None,
) -> IdentityStateLoadResult:
    """Fail-soft read: missing is uninitialized; unsafe/malformed is blocked."""
    try:
        identity = _coerce_identity(identity_or_repo)
    except (
        IdentityStateError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        error = f"repository identity input is invalid: {exc}"
        fallback_identity = build_repository_identity(Path.cwd())
        return IdentityStateLoadResult(
            exists=False,
            valid=False,
            status=IDENTITY_STATUS_BLOCKED,
            path="",
            state=_blocked_state(fallback_identity, (error,)),
            errors=(error,),
        )
    try:
        path = get_repository_identity_state_path(
            identity,
            repository_intelligence_root=repository_intelligence_root,
        )
    except (
        IdentityStateError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        blocked = _blocked_state(identity, (str(exc),))
        return IdentityStateLoadResult(
            exists=False,
            valid=False,
            status=IDENTITY_STATUS_BLOCKED,
            path="",
            state=blocked,
            errors=(str(exc),),
        )
    try:
        root = path.parent.parent
        _assert_safe_state_path(root, path)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        try:
            _assert_safe_state_path(path.parent.parent, path)
        except (
            IdentityStateError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            blocked = _blocked_state(identity, (str(exc),))
            return IdentityStateLoadResult(
                exists=False,
                valid=False,
                status=IDENTITY_STATUS_BLOCKED,
                path=str(path),
                state=blocked,
                errors=(str(exc),),
            )
        return IdentityStateLoadResult(
            exists=False,
            valid=True,
            status=IDENTITY_STATUS_UNINITIALIZED,
            path=str(path),
            state=build_uninitialized_identity_state(identity),
        )
    except (
        IdentityStateError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        blocked = _blocked_state(identity, (str(exc),))
        return IdentityStateLoadResult(
            exists=True,
            valid=False,
            status=IDENTITY_STATUS_BLOCKED,
            path=str(path),
            state=blocked,
            errors=(str(exc),),
        )
    try:
        with os.fdopen(descriptor, "rb", buffering=0) as handle:
            _assert_safe_state_path(root, path)
            _assert_open_artifact_identity(
                handle,
                path,
                label="identity-state artifact",
                require_empty=False,
            )
            if os.fstat(handle.fileno()).st_size > MAX_IDENTITY_STATE_BYTES:
                raise IdentityStateStorageError(
                    "identity-state artifact exceeds the "
                    f"{MAX_IDENTITY_STATE_BYTES}-byte read bound"
                )
            payload = handle.read(MAX_IDENTITY_STATE_BYTES + 1)
            _assert_safe_state_path(root, path)
            _assert_open_artifact_identity(
                handle,
                path,
                label="identity-state artifact",
                require_empty=False,
            )
        if len(payload) > MAX_IDENTITY_STATE_BYTES:
            raise IdentityStateStorageError(
                "identity-state artifact exceeds the "
                f"{MAX_IDENTITY_STATE_BYTES}-byte read bound"
            )
    except (
        IdentityStateError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        blocked = _blocked_state(identity, (str(exc),))
        return IdentityStateLoadResult(
            exists=True,
            valid=False,
            status=IDENTITY_STATUS_BLOCKED,
            path=str(path),
            state=blocked,
            errors=(str(exc),),
        )
    return parse_repository_identity_state(
        payload,
        expected_identity=identity,
        path=str(path),
    )


def _process_local_path_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path.absolute()))
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


def _prepare_state_directory(path: Path) -> None:
    root = path.parent.parent
    _assert_safe_state_path(root, path)
    root.mkdir(parents=True, exist_ok=True)
    _assert_safe_state_path(root, path)
    path.parent.mkdir(exist_ok=True)
    _assert_safe_state_path(root, path)


def _assert_open_lock_identity(handle: Any, lock_path: Path) -> None:
    _assert_open_artifact_identity(
        handle,
        lock_path,
        label="identity-state lock",
        require_empty=True,
    )


@contextmanager
def _interprocess_state_lock(path: Path) -> Iterator[None]:
    """Hold one OS-backed advisory lock for this repository identity."""
    root = path.parent.parent
    lock_path = path.with_name(IDENTITY_STATE_LOCK_FILENAME)
    _assert_safe_lock_path(root, lock_path)
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    handle = os.fdopen(descriptor, "r+b", buffering=0)
    locked = False
    try:
        _assert_open_lock_identity(handle, lock_path)
        handle.seek(0)
        deadline = time.monotonic() + INTERPROCESS_LOCK_TIMEOUT_SECONDS
        while not locked:
            try:
                if os.name == "nt":
                    msvcrt.locking(
                        handle.fileno(),
                        msvcrt.LK_NBLCK,
                        1,
                    )
                else:
                    fcntl.flock(
                        handle.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )
                locked = True
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise IdentityStateStorageError(
                        "timed out waiting for the repository identity-state "
                        "write lock"
                    ) from exc
                time.sleep(0.05)
                handle.seek(0)
        _assert_safe_lock_path(root, lock_path)
        _assert_open_lock_identity(handle, lock_path)
        _assert_safe_state_path(root, path)
        yield
    finally:
        if locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(
                        handle.fileno(),
                        msvcrt.LK_UNLCK,
                        1,
                    )
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                # Closing the descriptor still releases an OS-owned lock.
                pass
        handle.close()


@contextmanager
def _path_lock(
    path: Path,
) -> Iterator[IdentityStateError | OSError | None]:
    """Combine thread and process coordination, yielding acquisition errors."""
    with _process_local_path_lock(path):
        try:
            _prepare_state_directory(path)
        except (
            IdentityStateError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            yield exc
            return
        manager = _interprocess_state_lock(path)
        try:
            manager.__enter__()
        except (
            IdentityStateError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            yield exc
            return
        try:
            yield None
        finally:
            manager.__exit__(None, None, None)


def _save_failure(
    *,
    path: Path,
    state: RepositoryIdentityState,
    previous_revision: int,
    errors: Sequence[str],
) -> IdentityStateSaveResult:
    return IdentityStateSaveResult(
        ok=False,
        path=str(path),
        state=state,
        previous_revision=previous_revision,
        revision=state.state_revision,
        replaced=False,
        errors=tuple(sorted(set(str(error) for error in errors))),
    )


def save_repository_identity_state(
    state: RepositoryIdentityState | Mapping[str, Any],
    *,
    identity: RepositoryIdentity | str | os.PathLike[str],
    repository_intelligence_root: str | os.PathLike[str] | None = None,
    expected_revision: int | None = None,
) -> IdentityStateSaveResult:
    """Validate the on-disk transition and atomically replace the state file.

    The current artifact is reread while holding both process-local and
    OS-backed per-path locks, so revision validation and replacement form one
    cross-process compare-and-swap section. Malformed/blocked state is never
    repaired here. A future explicit repair phase must own that authority.
    """
    expected_identity = _coerce_identity(identity)
    if isinstance(state, Mapping) and not isinstance(
        state, RepositoryIdentityState
    ):
        try:
            state_value = _state_from_mapping(copy.deepcopy(dict(state)))
        except (
            IdentityStateError,
            RecursionError,
            TypeError,
            ValueError,
        ) as exc:
            fallback_path = Path("")
            try:
                fallback_path = get_repository_identity_state_path(
                    expected_identity,
                    repository_intelligence_root=(
                        repository_intelligence_root
                    ),
                )
            except (
                IdentityStateError,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ):
                pass
            return _save_failure(
                path=fallback_path,
                state=_blocked_state(expected_identity, (str(exc),)),
                previous_revision=0,
                errors=(str(exc),),
            )
    elif isinstance(state, RepositoryIdentityState):
        state_value = state
    else:
        raise TypeError(
            "state must be RepositoryIdentityState or a state mapping"
        )

    validation = validate_repository_identity_state(
        state_value,
        expected_identity=expected_identity,
    )
    if not validation.valid:
        try:
            invalid_path = get_repository_identity_state_path(
                expected_identity,
                repository_intelligence_root=repository_intelligence_root,
            )
        except (
            IdentityStateError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            invalid_path = Path("")
        return _save_failure(
            path=invalid_path,
            state=state_value,
            previous_revision=0,
            errors=validation.errors,
        )
    try:
        path = get_repository_identity_state_path(
            expected_identity,
            repository_intelligence_root=repository_intelligence_root,
        )
    except (
        IdentityStateError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        return _save_failure(
            path=Path(""),
            state=state_value,
            previous_revision=0,
            errors=(str(exc),),
        )

    with _path_lock(path) as lock_error:
        if lock_error is not None:
            return _save_failure(
                path=path,
                state=state_value,
                previous_revision=0,
                errors=(str(lock_error),),
            )
        current = load_repository_identity_state(
            expected_identity,
            repository_intelligence_root=repository_intelligence_root,
        )
        previous_revision = (
            current.state.state_revision if current.exists else 0
        )
        if not current.valid:
            return _save_failure(
                path=path,
                state=state_value,
                previous_revision=previous_revision,
                errors=(
                    "existing identity state is blocked and cannot self-heal",
                    *current.errors,
                ),
            )
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision != previous_revision
        ):
            return _save_failure(
                path=path,
                state=state_value,
                previous_revision=previous_revision,
                errors=(
                    f"stale expected_revision: expected "
                    f"{previous_revision}, received {expected_revision}",
                ),
            )
        current_state = current.state if current.exists else None
        transition = validate_identity_state_transition(
            current_state,
            state_value,
        )
        if not transition.allowed:
            return _save_failure(
                path=path,
                state=state_value,
                previous_revision=previous_revision,
                errors=transition.errors,
            )
        if current_state is not None and (
            current_state.to_dict() == state_value.to_dict()
        ):
            return IdentityStateSaveResult(
                ok=True,
                path=str(path),
                state=state_value,
                previous_revision=previous_revision,
                revision=state_value.state_revision,
                replaced=False,
            )
        try:
            payload = serialize_repository_identity_state(state_value)
            root = path.parent.parent
            root.mkdir(parents=True, exist_ok=True)
            _assert_safe_state_path(root, path)
            path.parent.mkdir(exist_ok=True)
            _assert_safe_state_path(root, path)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=str(path.parent),
                prefix=".identity_state.",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                _assert_safe_state_path(root, path)
                if temporary_path.parent != path.parent:
                    raise IdentityStateStorageError(
                        "temporary state file is not on the target volume"
                    )
                os.replace(temporary_path, path)
            finally:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
        except (
            OSError,
            IdentityStateError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            return _save_failure(
                path=path,
                state=state_value,
                previous_revision=previous_revision,
                errors=(str(exc),),
            )
    return IdentityStateSaveResult(
        ok=True,
        path=str(path),
        state=state_value,
        previous_revision=previous_revision,
        revision=state_value.state_revision,
        replaced=True,
    )


def save_repository_identity_transition(
    repository_intelligence_root: str | os.PathLike[str],
    identity: RepositoryIdentity | str | os.PathLike[str],
    transition: IdentityTransitionResult,
    *,
    expected_revision: int | None = None,
) -> IdentityStateSaveResult:
    """Persist only an applied, valid transition result."""
    if not transition.valid or not transition.applied:
        expected_identity = _coerce_identity(identity)
        path = get_repository_identity_state_path(
            expected_identity,
            repository_intelligence_root=repository_intelligence_root,
        )
        return _save_failure(
            path=path,
            state=transition.state,
            previous_revision=(
                transition.state.state_revision
                if expected_revision is None
                else expected_revision
            ),
            errors=(
                "only an applied valid identity transition may be saved",
                *transition.errors,
            ),
        )
    return save_repository_identity_state(
        transition.state,
        identity=identity,
        repository_intelligence_root=repository_intelligence_root,
        expected_revision=expected_revision,
    )
