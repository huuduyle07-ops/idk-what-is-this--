"""ACQUIRE.3 immutable contracts for bounded content acquisition.

This module contains records, bounded vocabularies and deterministic
fingerprints only.  The narrow read implementation lives in
``core.evidence_content_acquisition``.

The epistemic distinction is structural:

    eligible candidate -> acquired source -> future verified evidence

An acquired source records exact bytes and a digest, but it is always
``unverified`` and its authority is always ``not_verified``.  Payload bytes are
kept in a separate in-memory object and are deliberately absent from every
ordinary receipt serializer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from core.acquisition_request import (
    FRESHNESS_REQUIREMENTS,
    MAX_CANDIDATES_CEILING,
    MAX_INITIAL_SOURCES_CEILING,
    MAX_PER_SOURCE_BYTES_CEILING,
    MAX_TOTAL_BYTES_CEILING,
    REQUESTABLE_SOURCE_CLASSES,
)
from core.evidence_requirements import (
    ACTIVE_TIERS,
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    EVIDENCE_DOMAINS,
    EVIDENCE_ROLES,
)
from core.execution_waiter import WORKFLOW_TARGETS


PHASE_ID = "ACQUIRE.3"
SELECTION_SCHEMA_VERSION = "acquire_3_acquisition_selection_v1"
AUTHORIZATION_SCHEMA_VERSION = "acquire_3_acquisition_authorization_v1"
SOURCE_RECEIPT_SCHEMA_VERSION = "acquire_3_source_receipt_v1"
RESULT_SCHEMA_VERSION = "acquire_3_content_acquisition_result_v1"

# Selection provenance.  ACQUIRE.3 validates all three identically and never
# executes a selector itself.
SELECTION_SOURCE_HUMAN = "human_selection"
SELECTION_SOURCE_CTX_SELECT = "ctx_select_output"
SELECTION_SOURCE_AUTHORIZED_SELECTOR = "authorized_selector_output"
SELECTION_SOURCES: tuple[str, ...] = (
    SELECTION_SOURCE_HUMAN,
    SELECTION_SOURCE_CTX_SELECT,
    SELECTION_SOURCE_AUTHORIZED_SELECTOR,
)

# Authorization reason codes.  These are audit facts, not prose or credentials.
AUTHORIZATION_EXPLICIT_HUMAN_APPROVAL = "AUTHORIZATION_EXPLICIT_HUMAN_APPROVAL"
AUTHORIZATION_BOUNDED_REPOSITORY_READ = "AUTHORIZATION_BOUNDED_REPOSITORY_READ"
AUTHORIZATION_EXISTING_CONTEXT_REFERENCE = (
    "AUTHORIZATION_EXISTING_CONTEXT_REFERENCE"
)
AUTHORIZATION_EXTERNAL_DISCOVERY_ACKNOWLEDGED = (
    "AUTHORIZATION_EXTERNAL_DISCOVERY_ACKNOWLEDGED"
)
AUTHORIZATION_REASONS: tuple[str, ...] = (
    AUTHORIZATION_EXPLICIT_HUMAN_APPROVAL,
    AUTHORIZATION_BOUNDED_REPOSITORY_READ,
    AUTHORIZATION_EXISTING_CONTEXT_REFERENCE,
    AUTHORIZATION_EXTERNAL_DISCOVERY_ACKNOWLEDGED,
)

# Acquisition modes and immutable epistemic states.
MODE_REPOSITORY_READ = "repository_read"
MODE_EXISTING_CONTEXT = "existing_context"
ACQUISITION_MODES: tuple[str, ...] = (
    MODE_REPOSITORY_READ,
    MODE_EXISTING_CONTEXT,
)

SOURCE_ACQUIRED = "acquired"
SOURCE_ALREADY_AVAILABLE_REFERENCE = "already_available_reference"
SOURCE_ACQUISITION_STATUSES: tuple[str, ...] = (
    SOURCE_ACQUIRED,
    SOURCE_ALREADY_AVAILABLE_REFERENCE,
)

VERIFICATION_UNVERIFIED = "unverified"
AUTHORITY_NOT_VERIFIED = "not_verified"

# Per-source failures.  None authorizes substitution.
FAILURE_CANDIDATE_MISSING = "candidate_missing"
FAILURE_CANDIDATE_STALE = "candidate_stale"
FAILURE_STALE_DURING_ACQUISITION = "stale_during_acquisition"
FAILURE_UNSAFE_PATH = "unsafe_repository_path"
FAILURE_SYMLINK_REJECTED = "repository_symlink_rejected"
FAILURE_NON_REGULAR_FILE = "non_regular_file"
FAILURE_PER_SOURCE_BUDGET = "per_source_budget_exceeded"
FAILURE_TOTAL_BYTE_BUDGET = "total_byte_budget_exceeded"
FAILURE_REQUEST_SOURCE_BUDGET = "request_source_budget_exceeded"
FAILURE_REQUEST_BYTE_BUDGET = "request_byte_budget_exceeded"
FAILURE_READ_ERROR = "read_error"
SOURCE_FAILURE_CODES: tuple[str, ...] = (
    FAILURE_CANDIDATE_MISSING,
    FAILURE_CANDIDATE_STALE,
    FAILURE_STALE_DURING_ACQUISITION,
    FAILURE_UNSAFE_PATH,
    FAILURE_SYMLINK_REJECTED,
    FAILURE_NON_REGULAR_FILE,
    FAILURE_PER_SOURCE_BUDGET,
    FAILURE_TOTAL_BYTE_BUDGET,
    FAILURE_REQUEST_SOURCE_BUDGET,
    FAILURE_REQUEST_BYTE_BUDGET,
    FAILURE_READ_ERROR,
)

# Result statuses.
STATUS_ACQUIRED = "acquired"
STATUS_PARTIAL = "partial"
STATUS_AUTHORIZATION_REQUIRED = "authorization_required"
STATUS_BLOCKED = "blocked"
STATUS_STALE_CANDIDATES = "stale_candidates"
STATUS_BUDGET_BLOCKED = "budget_blocked"
STATUS_EXTERNAL_DISCOVERY_REQUIRED = "external_discovery_required"
ACQUISITION_RESULT_STATUSES: tuple[str, ...] = (
    STATUS_ACQUIRED,
    STATUS_PARTIAL,
    STATUS_AUTHORIZATION_REQUIRED,
    STATUS_BLOCKED,
    STATUS_STALE_CANDIDATES,
    STATUS_BUDGET_BLOCKED,
    STATUS_EXTERNAL_DISCOVERY_REQUIRED,
)

# Result reason codes.
ACQUISITION_AUTHORIZATION_REQUIRED = "ACQUISITION_AUTHORIZATION_REQUIRED"
ACQUISITION_AUTHORIZATION_VALIDATED = "ACQUISITION_AUTHORIZATION_VALIDATED"
ACQUISITION_SELECTION_VALIDATED = "ACQUISITION_SELECTION_VALIDATED"
ACQUISITION_REPOSITORY_SOURCES_ACQUIRED = (
    "ACQUISITION_REPOSITORY_SOURCES_ACQUIRED"
)
ACQUISITION_DIRECT_CONTEXT_REFERENCED = "ACQUISITION_DIRECT_CONTEXT_REFERENCED"
ACQUISITION_EXTERNAL_DISCOVERY_REQUIRED = (
    "ACQUISITION_EXTERNAL_DISCOVERY_REQUIRED"
)
ACQUISITION_SOURCE_FAILURES_RECORDED = "ACQUISITION_SOURCE_FAILURES_RECORDED"
ACQUISITION_NO_SOURCE_ACQUIRED = "ACQUISITION_NO_SOURCE_ACQUIRED"
ACQUISITION_BUDGETS_RESPECTED = "ACQUISITION_BUDGETS_RESPECTED"
ACQUISITION_REASONS: tuple[str, ...] = (
    ACQUISITION_AUTHORIZATION_REQUIRED,
    ACQUISITION_AUTHORIZATION_VALIDATED,
    ACQUISITION_SELECTION_VALIDATED,
    ACQUISITION_REPOSITORY_SOURCES_ACQUIRED,
    ACQUISITION_DIRECT_CONTEXT_REFERENCED,
    ACQUISITION_EXTERNAL_DISCOVERY_REQUIRED,
    ACQUISITION_SOURCE_FAILURES_RECORDED,
    ACQUISITION_NO_SOURCE_ACQUIRED,
    ACQUISITION_BUDGETS_RESPECTED,
)

# Contract-level inconsistencies.  These fail before any candidate path is
# touched.
INCONSISTENT_UPSTREAM_SOURCE = "upstream_source_fingerprint_mismatch"
INCONSISTENT_CANDIDATE_RECEIPT = "candidate_receipt_fingerprint_mismatch"
INCONSISTENT_INVENTORY = "inventory_fingerprint_mismatch"
INCONSISTENT_REPOSITORY_IDENTITY = "repository_identity_mismatch"
INCONSISTENT_SELECTION_BINDING = "selection_binding_mismatch"
INCONSISTENT_SELECTION_OUTSIDE_POOL = "selection_outside_candidate_pool"
INCONSISTENT_SELECTION_DEFERRED = "deferred_candidate_selected"
INCONSISTENT_SELECTION_BUDGET = "selection_budget_exceeded"
INCONSISTENT_SELECTION_NOT_AUTHORIZED = "selection_outside_authorization"
INCONSISTENT_SELECTOR_ENVELOPE = "selector_envelope_violation"
INCONSISTENT_AUTHORIZATION_BINDING = "authorization_binding_mismatch"
INCONSISTENT_AUTHORIZATION_WIDENED = "authorization_widened_upstream_limits"
INCONSISTENT_AUTHORIZATION_CANDIDATE = "authorization_candidate_outside_pool"
INCONSISTENT_AUTHORIZATION_DOMAIN = "authorization_domain_outside_pool"
INCONSISTENT_REPOSITORY_ROOT_REQUIRED = "repository_root_required"
INCONSISTENT_REPOSITORY_ROOT_INVALID = "repository_root_invalid"
INCONSISTENT_SELECTION_EMPTY = "selection_empty"
ACQUISITION_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_UPSTREAM_SOURCE,
    INCONSISTENT_CANDIDATE_RECEIPT,
    INCONSISTENT_INVENTORY,
    INCONSISTENT_REPOSITORY_IDENTITY,
    INCONSISTENT_SELECTION_BINDING,
    INCONSISTENT_SELECTION_OUTSIDE_POOL,
    INCONSISTENT_SELECTION_DEFERRED,
    INCONSISTENT_SELECTION_BUDGET,
    INCONSISTENT_SELECTION_NOT_AUTHORIZED,
    INCONSISTENT_SELECTOR_ENVELOPE,
    INCONSISTENT_AUTHORIZATION_BINDING,
    INCONSISTENT_AUTHORIZATION_WIDENED,
    INCONSISTENT_AUTHORIZATION_CANDIDATE,
    INCONSISTENT_AUTHORIZATION_DOMAIN,
    INCONSISTENT_REPOSITORY_ROOT_REQUIRED,
    INCONSISTENT_REPOSITORY_ROOT_INVALID,
    INCONSISTENT_SELECTION_EMPTY,
)

MAX_SELECTED_CANDIDATES = MAX_INITIAL_SOURCES_CEILING
MAX_AUTHORIZED_CANDIDATES = MAX_INITIAL_SOURCES_CEILING
MAX_AUTHORIZATION_REASONS = len(AUTHORIZATION_REASONS)
MAX_RESULT_REASONS = len(ACQUISITION_REASONS)
MAX_RESULT_INCONSISTENCIES = len(ACQUISITION_INCONSISTENCIES)
MAX_REPOSITORY_ROOT_LENGTH = 4_096
MAX_SOURCE_IDENTIFIER_LENGTH = 1_024


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _require_sha256(value: str | None, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _ordered_vocabulary(
    values: tuple[str, ...],
    vocabulary: tuple[str, ...],
    label: str,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label}s must be a tuple")
    if len(set(values)) != len(values):
        raise ValueError(f"each {label} may be stated exactly once")
    for value in values:
        if value not in vocabulary:
            raise ValueError(f"unsupported {label}: {value!r}")
    expected = tuple(item for item in vocabulary if item in set(values))
    if values != expected:
        raise ValueError(f"{label}s must use canonical vocabulary order")


def _bounded_identifiers(
    values: tuple[str, ...],
    *,
    maximum: int,
    canonical: bool,
    label: str,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    if len(values) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")
    if any(
        not isinstance(item, str)
        or not item
        or len(item) > MAX_SOURCE_IDENTIFIER_LENGTH
        for item in values
    ):
        raise ValueError(f"{label} contains an empty or overlong identifier")
    try:
        for item in values:
            item.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must be UTF-8 encodable") from exc
    if len(set(values)) != len(values):
        raise ValueError(f"{label} may name each identifier once")
    if canonical:
        expected = tuple(sorted(values, key=lambda item: (item.casefold(), item)))
        if values != expected:
            raise ValueError(f"{label} must be canonically ordered")


def _typed_tuple(
    values: object,
    item_type: type,
    *,
    maximum: int,
    label: str,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be an immutable tuple")
    if len(values) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")
    if any(not isinstance(item, item_type) for item in values):
        raise TypeError(f"{label} contains an unsupported item type")


@dataclass(frozen=True, slots=True)
class AcquisitionSelection:
    """A caller-proposed ordered subset.  ACQUIRE.3 never creates one."""

    candidate_identifiers: tuple[str, ...]
    candidate_receipt_fingerprint: str
    acquisition_request_fingerprint: str
    inventory_fingerprint: str | None = None
    repository_identity: str | None = None
    source: str = SELECTION_SOURCE_HUMAN
    schema_version: str = SELECTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifiers(
            self.candidate_identifiers,
            maximum=MAX_SELECTED_CANDIDATES,
            canonical=True,
            label="selected candidates",
        )
        _require_sha256(
            self.candidate_receipt_fingerprint,
            "candidate receipt fingerprint",
        )
        _require_sha256(
            self.acquisition_request_fingerprint,
            "acquisition request fingerprint",
        )
        _require_sha256(self.inventory_fingerprint, "inventory fingerprint", optional=True)
        if self.repository_identity is not None and (
            not isinstance(self.repository_identity, str) or not self.repository_identity
        ):
            raise ValueError("repository_identity must be a non-empty string or None")
        if (self.inventory_fingerprint is None) != (self.repository_identity is None):
            raise ValueError(
                "selection inventory fingerprint and repository identity are paired"
            )
        if self.source not in SELECTION_SOURCES:
            raise ValueError(f"unsupported selection source: {self.source!r}")
        if self.schema_version != SELECTION_SCHEMA_VERSION:
            raise ValueError("unsupported acquisition-selection schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_identifiers": list(self.candidate_identifiers),
            "candidate_receipt_fingerprint": self.candidate_receipt_fingerprint,
            "acquisition_request_fingerprint": self.acquisition_request_fingerprint,
            "inventory_fingerprint": self.inventory_fingerprint,
            "repository_identity": self.repository_identity,
            "source": self.source,
            "ordered": True,
            "generated_by_acquire_3": False,
        }


@dataclass(frozen=True, slots=True)
class AcquisitionAuthorization:
    """A narrow external grant.  Absence/default values authorize no read."""

    acquisition_allowed: bool = False
    human_approved: bool = False
    candidate_pool_fingerprint: str | None = None
    acquisition_request_fingerprint: str | None = None
    inventory_fingerprint: str | None = None
    repository_identity: str | None = None
    repository_root: str | None = None
    allowed_candidate_identifiers: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ()
    max_sources: int = 0
    max_total_bytes: int = 0
    max_per_source_bytes: int = 0
    reasons: tuple[str, ...] = ()
    schema_version: str = AUTHORIZATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.acquisition_allowed, bool):
            raise TypeError("acquisition_allowed must be a bool")
        if not isinstance(self.human_approved, bool):
            raise TypeError("human_approved must be a bool")
        _require_sha256(
            self.candidate_pool_fingerprint,
            "candidate pool fingerprint",
            optional=True,
        )
        _require_sha256(
            self.acquisition_request_fingerprint,
            "acquisition request fingerprint",
            optional=True,
        )
        _require_sha256(self.inventory_fingerprint, "inventory fingerprint", optional=True)
        if self.repository_identity is not None and (
            not isinstance(self.repository_identity, str) or not self.repository_identity
        ):
            raise ValueError("repository_identity must be a non-empty string or None")
        if (self.inventory_fingerprint is None) != (self.repository_identity is None):
            raise ValueError(
                "authorization inventory fingerprint and repository identity are paired"
            )
        if self.repository_root is not None:
            if not isinstance(self.repository_root, str) or not self.repository_root:
                raise ValueError("repository_root must be a non-empty string or None")
            if len(self.repository_root) > MAX_REPOSITORY_ROOT_LENGTH:
                raise ValueError("repository_root exceeds its finite bound")
            try:
                self.repository_root.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("repository_root must be UTF-8 encodable") from exc
            if any(ord(character) < 32 for character in self.repository_root):
                raise ValueError("repository_root may not contain control characters")
            if self.repository_root.startswith(("\\\\", "//")):
                raise ValueError("network-share repository roots are not supported")
            if self.repository_identity is None:
                raise ValueError("a repository root requires bound repository identity")
        _bounded_identifiers(
            self.allowed_candidate_identifiers,
            maximum=MAX_AUTHORIZED_CANDIDATES,
            canonical=True,
            label="authorized candidates",
        )
        _ordered_vocabulary(self.allowed_domains, EVIDENCE_DOMAINS, "authorized domain")
        for name, ceiling in (
            ("max_sources", MAX_INITIAL_SOURCES_CEILING),
            ("max_total_bytes", MAX_TOTAL_BYTES_CEILING),
            ("max_per_source_bytes", MAX_PER_SOURCE_BYTES_CEILING),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative integer")
            if value > ceiling:
                raise ValueError(f"{name} exceeds the global acquisition ceiling")
        _ordered_vocabulary(self.reasons, AUTHORIZATION_REASONS, "authorization reason")
        if len(self.reasons) > MAX_AUTHORIZATION_REASONS:
            raise ValueError("authorization reasons exceed their finite bound")
        if self.human_approved and (
            AUTHORIZATION_EXPLICIT_HUMAN_APPROVAL not in self.reasons
        ):
            raise ValueError("human approval must be recorded as a structured reason")
        domain_reasons = (
            (
                bool(
                    set(self.allowed_domains)
                    & {DOMAIN_REPOSITORY, DOMAIN_VALIDATION_ARTIFACTS}
                ),
                AUTHORIZATION_BOUNDED_REPOSITORY_READ,
            ),
            (
                DOMAIN_DIRECT_CONTEXT in self.allowed_domains,
                AUTHORIZATION_EXISTING_CONTEXT_REFERENCE,
            ),
            (
                DOMAIN_EXTERNAL_INFORMATION in self.allowed_domains,
                AUTHORIZATION_EXTERNAL_DISCOVERY_ACKNOWLEDGED,
            ),
        )
        for required, reason in domain_reasons:
            if required and reason not in self.reasons:
                raise ValueError("every authorized domain requires its structured reason")
        if self.schema_version != AUTHORIZATION_SCHEMA_VERSION:
            raise ValueError("unsupported acquisition-authorization schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "acquisition_allowed": self.acquisition_allowed,
            "human_approved": self.human_approved,
            "candidate_pool_fingerprint": self.candidate_pool_fingerprint,
            "acquisition_request_fingerprint": self.acquisition_request_fingerprint,
            "inventory_fingerprint": self.inventory_fingerprint,
            "repository_identity": self.repository_identity,
            "repository_root": self.repository_root,
            "allowed_candidate_identifiers": list(self.allowed_candidate_identifiers),
            "allowed_domains": list(self.allowed_domains),
            "max_sources": self.max_sources,
            "max_total_bytes": self.max_total_bytes,
            "max_per_source_bytes": self.max_per_source_bytes,
            "reasons": list(self.reasons),
            "bounded": True,
            "minted_by_acquire_3": False,
        }


def selection_fingerprint(selection: AcquisitionSelection) -> str:
    if not isinstance(selection, AcquisitionSelection):
        raise TypeError("selection_fingerprint requires an AcquisitionSelection")
    return _fingerprint(selection.as_dict())


def authorization_fingerprint(authorization: AcquisitionAuthorization) -> str:
    if not isinstance(authorization, AcquisitionAuthorization):
        raise TypeError(
            "authorization_fingerprint requires an AcquisitionAuthorization"
        )
    return _fingerprint(authorization.as_dict())


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """Tamper-evident identity chain for one acquired source."""

    candidate_identifier: str
    acquisition_mode: str
    task_contract_fingerprint: str
    completion_fingerprint: str
    waiter_decision_fingerprint: str
    evidence_requirement_fingerprint: str
    acquisition_request_fingerprint: str
    candidate_receipt_fingerprint: str
    selection_fingerprint: str
    authorization_fingerprint: str
    inventory_fingerprint: str | None = None
    repository_identity: str | None = None

    def __post_init__(self) -> None:
        _bounded_identifiers(
            (self.candidate_identifier,),
            maximum=1,
            canonical=False,
            label="source binding candidate identifier",
        )
        if self.acquisition_mode not in ACQUISITION_MODES:
            raise ValueError(f"unsupported acquisition mode: {self.acquisition_mode!r}")
        for name in (
            "task_contract_fingerprint",
            "completion_fingerprint",
            "waiter_decision_fingerprint",
            "evidence_requirement_fingerprint",
            "acquisition_request_fingerprint",
            "candidate_receipt_fingerprint",
            "selection_fingerprint",
            "authorization_fingerprint",
        ):
            _require_sha256(getattr(self, name), name.replace("_", " "))
        _require_sha256(self.inventory_fingerprint, "inventory fingerprint", optional=True)
        if self.repository_identity is not None and (
            not isinstance(self.repository_identity, str) or not self.repository_identity
        ):
            raise ValueError("repository_identity must be a non-empty string or None")
        if (self.inventory_fingerprint is None) != (self.repository_identity is None):
            raise ValueError(
                "source-binding inventory fingerprint and repository identity are paired"
            )
        if self.acquisition_mode == MODE_REPOSITORY_READ and (
            self.inventory_fingerprint is None or self.repository_identity is None
        ):
            raise ValueError("repository bindings require inventory and repository identity")
        if self.acquisition_mode == MODE_EXISTING_CONTEXT and (
            self.inventory_fingerprint is not None or self.repository_identity is not None
        ):
            raise ValueError("existing context is not bound to a repository inventory")

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_identifier": self.candidate_identifier,
            "acquisition_mode": self.acquisition_mode,
            "task_contract_fingerprint": self.task_contract_fingerprint,
            "completion_fingerprint": self.completion_fingerprint,
            "waiter_decision_fingerprint": self.waiter_decision_fingerprint,
            "evidence_requirement_fingerprint": self.evidence_requirement_fingerprint,
            "acquisition_request_fingerprint": self.acquisition_request_fingerprint,
            "candidate_receipt_fingerprint": self.candidate_receipt_fingerprint,
            "selection_fingerprint": self.selection_fingerprint,
            "authorization_fingerprint": self.authorization_fingerprint,
            "inventory_fingerprint": self.inventory_fingerprint,
            "repository_identity": self.repository_identity,
        }


@dataclass(frozen=True, slots=True, repr=False)
class AcquiredSourcePayload:
    """Ephemeral exact bytes.  There is intentionally no ``as_dict`` method."""

    candidate_identifier: str
    content: bytes = field(repr=False)
    content_sha256: str
    bytes_acquired: int
    source_binding: SourceBinding

    def __post_init__(self) -> None:
        _bounded_identifiers(
            (self.candidate_identifier,),
            maximum=1,
            canonical=False,
            label="payload candidate identifier",
        )
        if not isinstance(self.content, bytes):
            raise TypeError("an acquired payload is exact bytes")
        if self.bytes_acquired != len(self.content):
            raise ValueError("payload byte count must equal its exact content length")
        _require_sha256(self.content_sha256, "content SHA-256")
        if hashlib.sha256(self.content).hexdigest() != self.content_sha256:
            raise ValueError("payload content does not match its SHA-256")
        if not isinstance(self.source_binding, SourceBinding):
            raise TypeError("payload source_binding must be a SourceBinding")
        if self.source_binding.candidate_identifier != self.candidate_identifier:
            raise ValueError("payload and source binding name different candidates")
        if self.source_binding.acquisition_mode != MODE_REPOSITORY_READ:
            raise ValueError("byte payloads must carry a repository-read binding")
        if self.bytes_acquired > MAX_PER_SOURCE_BYTES_CEILING:
            raise ValueError("payload exceeds the hard per-source byte ceiling")


@dataclass(frozen=True, slots=True)
class SourceAcquisitionReceipt:
    """Serializable receipt for exact bytes, never the bytes themselves."""

    candidate_identifier: str
    domain: str
    tier: str
    expected_roles: tuple[str, ...]
    eligible_source_classes: tuple[str, ...]
    target_artifact: bool
    content_sha256: str
    bytes_acquired: int
    source_binding: SourceBinding
    acquisition_status: str = SOURCE_ACQUIRED
    verification_status: str = VERIFICATION_UNVERIFIED
    authority_status: str = AUTHORITY_NOT_VERIFIED
    acquisition_mode: str = MODE_REPOSITORY_READ
    schema_version: str = SOURCE_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifiers(
            (self.candidate_identifier,),
            maximum=1,
            canonical=False,
            label="source receipt candidate identifier",
        )
        if self.domain not in {DOMAIN_REPOSITORY, DOMAIN_VALIDATION_ARTIFACTS}:
            raise ValueError("byte source receipts require a repository-backed domain")
        if self.tier not in ACTIVE_TIERS:
            raise ValueError("byte source receipts require an active tier")
        _ordered_vocabulary(self.expected_roles, EVIDENCE_ROLES, "expected role")
        _ordered_vocabulary(
            self.eligible_source_classes,
            REQUESTABLE_SOURCE_CLASSES,
            "eligible source class",
        )
        if not isinstance(self.target_artifact, bool):
            raise TypeError("target_artifact must be a bool")
        _require_sha256(self.content_sha256, "content SHA-256")
        if isinstance(self.bytes_acquired, bool) or not isinstance(
            self.bytes_acquired, int
        ) or self.bytes_acquired < 0:
            raise ValueError("bytes_acquired must be a finite non-negative integer")
        if self.acquisition_status != SOURCE_ACQUIRED:
            raise ValueError("a successful source receipt must say acquired")
        if self.verification_status != VERIFICATION_UNVERIFIED:
            raise ValueError("ACQUIRE.3 source receipts are always unverified")
        if self.authority_status != AUTHORITY_NOT_VERIFIED:
            raise ValueError("ACQUIRE.3 never verifies source authority")
        if self.acquisition_mode != MODE_REPOSITORY_READ:
            raise ValueError("a byte-bearing source receipt uses repository_read")
        if not isinstance(self.source_binding, SourceBinding):
            raise TypeError("receipt source_binding must be a SourceBinding")
        if self.source_binding.candidate_identifier != self.candidate_identifier:
            raise ValueError("receipt and source binding name different candidates")
        if self.source_binding.acquisition_mode != self.acquisition_mode:
            raise ValueError("receipt and source binding use different acquisition modes")
        if self.bytes_acquired > MAX_PER_SOURCE_BYTES_CEILING:
            raise ValueError("receipt exceeds the hard per-source byte ceiling")
        if not self.target_artifact and (
            not self.expected_roles or not self.eligible_source_classes
        ):
            raise ValueError("a non-target source must carry expected classes and roles")
        if self.target_artifact and bool(self.expected_roles) != bool(
            self.eligible_source_classes
        ):
            raise ValueError(
                "a target is either roleless/classless or carries both expected facts"
            )
        if self.schema_version != SOURCE_RECEIPT_SCHEMA_VERSION:
            raise ValueError("unsupported source receipt schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_identifier": self.candidate_identifier,
            "domain": self.domain,
            "tier": self.tier,
            "expected_roles": list(self.expected_roles),
            "eligible_source_classes": list(self.eligible_source_classes),
            "target_artifact": self.target_artifact,
            "content_sha256": self.content_sha256,
            "bytes_acquired": self.bytes_acquired,
            "acquisition_status": self.acquisition_status,
            "verification_status": self.verification_status,
            "authority_status": self.authority_status,
            "acquisition_mode": self.acquisition_mode,
            "source_binding": self.source_binding.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class SourceAcquisitionFailure:
    candidate_identifier: str
    domain: str
    tier: str
    failure_code: str
    expected_size_bytes: int | None = None
    bytes_acquired: int = 0

    def __post_init__(self) -> None:
        _bounded_identifiers(
            (self.candidate_identifier,),
            maximum=1,
            canonical=False,
            label="failed source candidate identifier",
        )
        if self.domain not in {DOMAIN_REPOSITORY, DOMAIN_VALIDATION_ARTIFACTS}:
            raise ValueError("source failures require a repository-backed domain")
        if self.tier not in ACTIVE_TIERS:
            raise ValueError("source failures require an active tier")
        if self.failure_code not in SOURCE_FAILURE_CODES:
            raise ValueError(f"unsupported source failure: {self.failure_code!r}")
        if (
            isinstance(self.expected_size_bytes, bool)
            or not isinstance(self.expected_size_bytes, int)
            or self.expected_size_bytes < 0
        ):
            raise ValueError("failed active sources require a non-negative expected size")
        if self.bytes_acquired != 0:
            raise ValueError("failed sources acquire zero accepted bytes")

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_identifier": self.candidate_identifier,
            "domain": self.domain,
            "tier": self.tier,
            "failure_code": self.failure_code,
            "expected_size_bytes": self.expected_size_bytes,
            "bytes_acquired": 0,
            "acquisition_status": "failed",
            "content_read_accepted": False,
            "substitution_performed": False,
        }


@dataclass(frozen=True, slots=True)
class DirectContextReceipt:
    candidate_identifier: str
    tier: str
    expected_roles: tuple[str, ...]
    eligible_source_classes: tuple[str, ...]
    source_binding: SourceBinding
    acquisition_mode: str = MODE_EXISTING_CONTEXT
    acquisition_status: str = SOURCE_ALREADY_AVAILABLE_REFERENCE
    verification_status: str = VERIFICATION_UNVERIFIED
    authority_status: str = AUTHORITY_NOT_VERIFIED

    def __post_init__(self) -> None:
        _bounded_identifiers(
            (self.candidate_identifier,),
            maximum=1,
            canonical=False,
            label="direct-context candidate identifier",
        )
        prefix = "supplied_context:"
        if not self.candidate_identifier.startswith(prefix):
            raise ValueError("direct context must use its canonical upstream identity")
        _require_sha256(
            self.candidate_identifier[len(prefix) :],
            "direct-context upstream fingerprint",
        )
        if self.tier not in ACTIVE_TIERS:
            raise ValueError("direct-context receipts require an active tier")
        _ordered_vocabulary(self.expected_roles, EVIDENCE_ROLES, "expected role")
        _ordered_vocabulary(
            self.eligible_source_classes,
            REQUESTABLE_SOURCE_CLASSES,
            "eligible source class",
        )
        if not self.expected_roles or not self.eligible_source_classes:
            raise ValueError("a direct-context reference must carry its expected role")
        if self.acquisition_mode != MODE_EXISTING_CONTEXT:
            raise ValueError("direct context uses existing_context mode")
        if self.acquisition_status != SOURCE_ALREADY_AVAILABLE_REFERENCE:
            raise ValueError("direct context is an already-available reference")
        if self.verification_status != VERIFICATION_UNVERIFIED:
            raise ValueError("direct context remains unverified")
        if self.authority_status != AUTHORITY_NOT_VERIFIED:
            raise ValueError("direct-context authority remains unverified")
        if not isinstance(self.source_binding, SourceBinding):
            raise TypeError("direct receipt source_binding must be a SourceBinding")
        if self.source_binding.candidate_identifier != self.candidate_identifier:
            raise ValueError("direct receipt and binding name different candidates")
        if self.source_binding.acquisition_mode != self.acquisition_mode:
            raise ValueError("direct receipt and binding use different acquisition modes")

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_identifier": self.candidate_identifier,
            "tier": self.tier,
            "expected_roles": list(self.expected_roles),
            "eligible_source_classes": list(self.eligible_source_classes),
            "acquisition_mode": self.acquisition_mode,
            "acquisition_status": self.acquisition_status,
            "verification_status": self.verification_status,
            "authority_status": self.authority_status,
            "source_binding": self.source_binding.as_dict(),
            "content_serialized": False,
        }


@dataclass(frozen=True, slots=True)
class ExternalDiscoveryRequirement:
    required_role: str
    allowed_source_classes: tuple[str, ...]
    freshness: str
    candidate_budget: int
    source_budget_reserved: int

    def __post_init__(self) -> None:
        if self.required_role not in EVIDENCE_ROLES:
            raise ValueError(f"unsupported evidence role: {self.required_role!r}")
        _ordered_vocabulary(
            self.allowed_source_classes,
            REQUESTABLE_SOURCE_CLASSES,
            "external source class",
        )
        if not self.allowed_source_classes:
            raise ValueError("external discovery must name its allowed source class")
        if self.freshness not in FRESHNESS_REQUIREMENTS:
            raise ValueError(f"unsupported freshness requirement: {self.freshness!r}")
        for name in ("candidate_budget", "source_budget_reserved"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative integer")
        if self.candidate_budget > MAX_CANDIDATES_CEILING:
            raise ValueError("external candidate budget exceeds the hard ceiling")
        if self.source_budget_reserved > MAX_INITIAL_SOURCES_CEILING:
            raise ValueError("external source budget exceeds the hard ceiling")

    def as_dict(self) -> dict[str, Any]:
        return {
            "required_role": self.required_role,
            "allowed_source_classes": list(self.allowed_source_classes),
            "freshness": self.freshness,
            "candidate_budget": self.candidate_budget,
            "source_budget_reserved": self.source_budget_reserved,
            "status": STATUS_EXTERNAL_DISCOVERY_REQUIRED,
            "concrete_candidates": [],
            "query_generated": False,
            "network_called": False,
        }


@dataclass(frozen=True, slots=True)
class AcquisitionBudgetSummary:
    source_limit: int
    sources_acquired: int
    total_byte_limit: int
    bytes_acquired: int
    max_per_source_bytes: int
    sources_selected: int = 0
    bytes_selected_reserved: int = 0
    bytes_read: int = 0

    def __post_init__(self) -> None:
        for name in (
            "source_limit",
            "sources_acquired",
            "total_byte_limit",
            "bytes_acquired",
            "max_per_source_bytes",
            "sources_selected",
            "bytes_selected_reserved",
            "bytes_read",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative integer")
        if self.sources_acquired > self.source_limit:
            raise ValueError("sources acquired may not exceed the source limit")
        if self.sources_selected > self.source_limit:
            raise ValueError("selected sources may not exceed the source limit")
        if self.sources_acquired > self.sources_selected:
            raise ValueError("acquired sources may not exceed the closed selection")
        if self.bytes_acquired > self.total_byte_limit:
            raise ValueError("bytes acquired may not exceed the total-byte limit")
        if self.bytes_selected_reserved > self.total_byte_limit:
            raise ValueError("selected bytes may not exceed the total-byte limit")
        if self.bytes_read > self.bytes_selected_reserved:
            raise ValueError("physical reads may not exceed selected reserved bytes")
        if self.bytes_acquired > self.bytes_read:
            raise ValueError("accepted bytes may not exceed physical bytes read")
        if self.source_limit > MAX_INITIAL_SOURCES_CEILING:
            raise ValueError("source limit exceeds the hard acquisition ceiling")
        if self.total_byte_limit > MAX_TOTAL_BYTES_CEILING:
            raise ValueError("total-byte limit exceeds the hard acquisition ceiling")
        if self.max_per_source_bytes > MAX_PER_SOURCE_BYTES_CEILING:
            raise ValueError("per-source limit exceeds the hard acquisition ceiling")

    @property
    def sources_remaining(self) -> int:
        return self.source_limit - self.sources_acquired

    @property
    def bytes_remaining(self) -> int:
        return self.total_byte_limit - self.bytes_acquired

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_limit": self.source_limit,
            "sources_acquired": self.sources_acquired,
            "sources_remaining": self.sources_remaining,
            "total_byte_limit": self.total_byte_limit,
            "bytes_acquired": self.bytes_acquired,
            "bytes_remaining": self.bytes_remaining,
            "max_per_source_bytes": self.max_per_source_bytes,
            "sources_selected": self.sources_selected,
            "bytes_selected_reserved": self.bytes_selected_reserved,
            "bytes_read": self.bytes_read,
            "selection_closed": True,
            "bounded": True,
            "within_source_limit": self.sources_acquired <= self.source_limit,
            "within_byte_limit": self.bytes_acquired <= self.total_byte_limit,
        }


def acquisition_authority(
    *,
    authorization_valid: bool,
    repository_scope_authorized: bool,
) -> dict[str, bool]:
    return {
        "candidate_content_read_authority": (
            authorization_valid and repository_scope_authorized
        ),
        "repository_read_authority": (
            authorization_valid and repository_scope_authorized
        ),
        "evidence_acquisition_authority": False,
        "repository_traversal_authority": False,
        "external_search_authority": False,
        "web_fetch_authority": False,
        "context_selection_execution_authority": False,
        "indexing_authority": False,
        "graph_authority": False,
        "validation_authority": False,
        "command_execution_authority": False,
        "worker_launch_authority": False,
        "repository_write_authority": False,
        "patch_authority": False,
        "planning_authority": False,
        "routing_authority": False,
        "provider_selection_authority": False,
        "model_selection_authority": False,
        "project_evolution_authority": False,
        "evidence_verification_authority": False,
        "claim_promotion_authority": False,
        "human_approval_required": True,
    }


def acquisition_guardrails(
    *,
    candidate_contents_read: bool,
    repository_files_read: bool,
    source_content_acquired: bool,
) -> dict[str, bool]:
    return {
        "source_content_acquired": source_content_acquired,
        "candidate_contents_read": candidate_contents_read,
        "repository_files_read": repository_files_read,
        "repository_traversal_performed": False,
        "new_inventory_built": False,
        "manifest_refreshed": False,
        "index_consulted": False,
        "graph_consulted": False,
        "ctx_select_executed": False,
        "network_called": False,
        "web_search_performed": False,
        "external_sources_fetched": False,
        "validation_executed": False,
        "planning_performed": False,
        "model_called": False,
        "provider_selected": False,
        "evidence_verified": False,
        "claim_promoted": False,
        "repository_written": False,
        "substitution_performed": False,
    }


@dataclass(frozen=True, slots=True)
class ContentAcquisitionResult:
    status: str
    workflow: str | None
    candidate_receipt_fingerprint: str
    acquisition_request_fingerprint: str
    selection_fingerprint: str
    authorization_fingerprint: str | None
    inventory_fingerprint: str | None
    repository_identity: str | None
    budget: AcquisitionBudgetSummary
    task_contract_fingerprint: str | None = None
    completion_fingerprint: str | None = None
    waiter_decision_fingerprint: str | None = None
    evidence_requirement_fingerprint: str | None = None
    payloads: tuple[AcquiredSourcePayload, ...] = field(default=(), repr=False)
    acquired_receipts: tuple[SourceAcquisitionReceipt, ...] = ()
    failed_receipts: tuple[SourceAcquisitionFailure, ...] = ()
    direct_context_receipts: tuple[DirectContextReceipt, ...] = ()
    unresolved_external_requests: tuple[ExternalDiscoveryRequirement, ...] = ()
    reasons: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()
    human_approval_present: bool = False
    acquisition_authorization_valid: bool = False
    repository_scope_authorized: bool = False
    candidate_contents_read: bool = False
    repository_files_read: bool = False
    schema_version: str = RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.budget, AcquisitionBudgetSummary):
            raise TypeError("result budget must be an AcquisitionBudgetSummary")
        for values, item_type, label in (
            (self.payloads, AcquiredSourcePayload, "result payloads"),
            (
                self.acquired_receipts,
                SourceAcquisitionReceipt,
                "acquired source receipts",
            ),
            (self.failed_receipts, SourceAcquisitionFailure, "failed source receipts"),
            (
                self.direct_context_receipts,
                DirectContextReceipt,
                "direct-context receipts",
            ),
            (
                self.unresolved_external_requests,
                ExternalDiscoveryRequirement,
                "unresolved external requests",
            ),
        ):
            _typed_tuple(
                values,
                item_type,
                maximum=MAX_INITIAL_SOURCES_CEILING,
                label=label,
            )
        if self.status not in ACQUISITION_RESULT_STATUSES:
            raise ValueError(f"unsupported acquisition result status: {self.status!r}")
        if self.workflow is not None and self.workflow not in WORKFLOW_TARGETS:
            raise ValueError(f"unsupported workflow: {self.workflow!r}")
        _require_sha256(
            self.candidate_receipt_fingerprint,
            "candidate receipt fingerprint",
        )
        _require_sha256(
            self.acquisition_request_fingerprint,
            "acquisition request fingerprint",
        )
        _require_sha256(self.selection_fingerprint, "selection fingerprint")
        _require_sha256(
            self.authorization_fingerprint,
            "authorization fingerprint",
            optional=True,
        )
        _require_sha256(self.inventory_fingerprint, "inventory fingerprint", optional=True)
        if self.repository_identity is not None and (
            not isinstance(self.repository_identity, str) or not self.repository_identity
        ):
            raise ValueError("repository_identity must be a non-empty string or None")
        if (self.inventory_fingerprint is None) != (self.repository_identity is None):
            raise ValueError(
                "result inventory fingerprint and repository identity are paired"
            )
        for name in (
            "task_contract_fingerprint",
            "completion_fingerprint",
            "waiter_decision_fingerprint",
            "evidence_requirement_fingerprint",
        ):
            _require_sha256(getattr(self, name), name.replace("_", " "), optional=True)
        _ordered_vocabulary(self.reasons, ACQUISITION_REASONS, "acquisition reason")
        _ordered_vocabulary(
            self.inconsistencies,
            ACQUISITION_INCONSISTENCIES,
            "acquisition inconsistency",
        )
        if len(self.reasons) > MAX_RESULT_REASONS:
            raise ValueError("result reasons exceed their finite bound")
        if len(self.inconsistencies) > MAX_RESULT_INCONSISTENCIES:
            raise ValueError("result inconsistencies exceed their finite bound")
        for name in (
            "human_approval_present",
            "acquisition_authorization_valid",
            "repository_scope_authorized",
            "candidate_contents_read",
            "repository_files_read",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if self.acquisition_authorization_valid and not self.human_approval_present:
            raise ValueError("valid acquisition authority requires human approval")
        if self.acquisition_authorization_valid and self.authorization_fingerprint is None:
            raise ValueError("valid acquisition authority requires its fingerprint")
        if self.repository_scope_authorized and not self.acquisition_authorization_valid:
            raise ValueError("repository scope cannot be authorized by an invalid grant")
        successes = bool(self.acquired_receipts or self.direct_context_receipts)
        outcomes = bool(
            successes
            or self.failed_receipts
            or self.unresolved_external_requests
        )
        if outcomes and not self.acquisition_authorization_valid:
            raise ValueError("source outcomes require validated acquisition authority")
        if successes and not (
            self.human_approval_present and self.acquisition_authorization_valid
        ):
            raise ValueError("successful acquisition requires valid human-approved authority")
        if (self.acquired_receipts or self.candidate_contents_read) and not (
            self.repository_scope_authorized
        ):
            raise ValueError("repository acquisition requires authorized repository scope")
        if self.repository_files_read != self.candidate_contents_read:
            raise ValueError("repository read guardrails must report the same performed fact")
        file_outcomes = bool(self.acquired_receipts or self.failed_receipts)
        if self.repository_scope_authorized != file_outcomes:
            raise ValueError(
                "repository scope authority must exactly match repository source outcomes"
            )
        if self.repository_scope_authorized and (
            self.inventory_fingerprint is None or self.repository_identity is None
        ):
            raise ValueError("repository scope requires inventory and repository identity")
        if len(self.payloads) != len(self.acquired_receipts):
            raise ValueError("every acquired receipt must have one ephemeral payload")
        for payload, receipt in zip(self.payloads, self.acquired_receipts):
            if (
                payload.candidate_identifier != receipt.candidate_identifier
                or payload.content_sha256 != receipt.content_sha256
                or payload.bytes_acquired != receipt.bytes_acquired
                or payload.source_binding != receipt.source_binding
            ):
                raise ValueError("payload and receipt do not describe the same bytes")

        if successes:
            for name in (
                "task_contract_fingerprint",
                "completion_fingerprint",
                "waiter_decision_fingerprint",
                "evidence_requirement_fingerprint",
                "authorization_fingerprint",
            ):
                if getattr(self, name) is None:
                    raise ValueError(
                        f"successful acquisition requires {name.replace('_', ' ')}"
                    )

        def validate_binding(binding: SourceBinding, *, repository: bool) -> None:
            expected = (
                self.task_contract_fingerprint,
                self.completion_fingerprint,
                self.waiter_decision_fingerprint,
                self.evidence_requirement_fingerprint,
                self.acquisition_request_fingerprint,
                self.candidate_receipt_fingerprint,
                self.selection_fingerprint,
                self.authorization_fingerprint,
                self.inventory_fingerprint if repository else None,
                self.repository_identity if repository else None,
            )
            actual = (
                binding.task_contract_fingerprint,
                binding.completion_fingerprint,
                binding.waiter_decision_fingerprint,
                binding.evidence_requirement_fingerprint,
                binding.acquisition_request_fingerprint,
                binding.candidate_receipt_fingerprint,
                binding.selection_fingerprint,
                binding.authorization_fingerprint,
                binding.inventory_fingerprint,
                binding.repository_identity,
            )
            if actual != expected:
                raise ValueError("source receipt binding contradicts result provenance")

        for receipt in self.acquired_receipts:
            validate_binding(receipt.source_binding, repository=True)
        for receipt in self.direct_context_receipts:
            validate_binding(receipt.source_binding, repository=False)
        identifiers = [
            item.candidate_identifier
            for group in (
                self.acquired_receipts,
                self.failed_receipts,
                self.direct_context_receipts,
            )
            for item in group
        ]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("one selected candidate may have exactly one result")
        unresolved = bool(self.failed_receipts or self.unresolved_external_requests)
        if self.status == STATUS_ACQUIRED and (not successes or unresolved):
            raise ValueError("acquired means at least one success and nothing unresolved")
        if self.status == STATUS_PARTIAL and (not successes or not unresolved):
            raise ValueError("partial requires both a success and an unresolved result")
        if self.status in {
            STATUS_AUTHORIZATION_REQUIRED,
            STATUS_BLOCKED,
            STATUS_STALE_CANDIDATES,
            STATUS_BUDGET_BLOCKED,
            STATUS_EXTERNAL_DISCOVERY_REQUIRED,
        } and successes:
            raise ValueError(f"status {self.status!r} may not carry a successful source")
        if self.status == STATUS_EXTERNAL_DISCOVERY_REQUIRED and not (
            self.unresolved_external_requests
        ):
            raise ValueError("external discovery status must name the unresolved request")
        if self.status == STATUS_EXTERNAL_DISCOVERY_REQUIRED and (
            self.failed_receipts or self.inconsistencies
        ):
            raise ValueError("external_discovery_required is an external-only outcome")
        stale_codes = {
            FAILURE_CANDIDATE_MISSING,
            FAILURE_CANDIDATE_STALE,
            FAILURE_STALE_DURING_ACQUISITION,
        }
        if self.status == STATUS_STALE_CANDIDATES and (
            not self.failed_receipts
            or any(item.failure_code not in stale_codes for item in self.failed_receipts)
            or self.unresolved_external_requests
        ):
            raise ValueError(
                "stale_candidates must carry only stale/missing failures and no other work"
            )
        if self.status == STATUS_AUTHORIZATION_REQUIRED and (
            outcomes or self.inconsistencies
        ):
            raise ValueError("authorization_required precedes source failures")
        if self.status == STATUS_BUDGET_BLOCKED and (
            self.failed_receipts or not self.inconsistencies
        ):
            raise ValueError("budget_blocked is a structural pre-read refusal")
        if self.status == STATUS_BLOCKED and not (
            self.failed_receipts or self.inconsistencies
        ):
            raise ValueError("blocked must state the failure or inconsistency")
        if (
            self.status == STATUS_BLOCKED
            and self.failed_receipts
            and not self.inconsistencies
            and not self.unresolved_external_requests
            and all(item.failure_code in stale_codes for item in self.failed_receipts)
        ):
            raise ValueError("stale-only failures require stale_candidates status")
        if self.budget.sources_acquired != (
            len(self.acquired_receipts) + len(self.direct_context_receipts)
        ):
            raise ValueError("budget source spending contradicts successful receipts")
        if self.budget.bytes_acquired != sum(
            item.bytes_acquired for item in self.acquired_receipts
        ):
            raise ValueError("budget byte spending contradicts acquired receipts")
        if any(
            item.bytes_acquired > self.budget.max_per_source_bytes
            for item in self.acquired_receipts
        ):
            raise ValueError("an acquired source exceeds the result per-source limit")
        reserved_bytes = sum(
            item.bytes_acquired for item in self.acquired_receipts
        ) + sum(
            int(item.expected_size_bytes or 0) for item in self.failed_receipts
        )
        if self.budget.bytes_selected_reserved != reserved_bytes:
            raise ValueError("budget reserved bytes contradict repository source outcomes")
        if self.budget.sources_selected != len(identifiers):
            raise ValueError("budget selection count contradicts source results")
        if self.acquired_receipts and not (
            self.candidate_contents_read and self.repository_files_read
        ):
            raise ValueError("repository receipts require truthful performed-read flags")
        if self.schema_version != RESULT_SCHEMA_VERSION:
            raise ValueError("unsupported content-acquisition result schema version")

    @property
    def source_content_acquired(self) -> bool:
        return bool(self.acquired_receipts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "status": self.status,
            "workflow": self.workflow,
            "candidate_receipt_fingerprint": self.candidate_receipt_fingerprint,
            "acquisition_request_fingerprint": self.acquisition_request_fingerprint,
            "selection_fingerprint": self.selection_fingerprint,
            "authorization_fingerprint": self.authorization_fingerprint,
            "inventory_fingerprint": self.inventory_fingerprint,
            "repository_identity": self.repository_identity,
            "task_contract_fingerprint": self.task_contract_fingerprint,
            "completion_fingerprint": self.completion_fingerprint,
            "waiter_decision_fingerprint": self.waiter_decision_fingerprint,
            "evidence_requirement_fingerprint": self.evidence_requirement_fingerprint,
            "acquired_receipts": [item.as_dict() for item in self.acquired_receipts],
            "failed_receipts": [item.as_dict() for item in self.failed_receipts],
            "direct_context_receipts": [
                item.as_dict() for item in self.direct_context_receipts
            ],
            "unresolved_external_requests": [
                item.as_dict() for item in self.unresolved_external_requests
            ],
            "budget": self.budget.as_dict(),
            "reasons": list(self.reasons),
            "inconsistencies": list(self.inconsistencies),
            "authorization_receipt": {
                "human_approval_present": self.human_approval_present,
                "acquisition_authorization_valid": (
                    self.acquisition_authorization_valid
                ),
                "authorization_fingerprint": self.authorization_fingerprint,
            },
            "authority": acquisition_authority(
                authorization_valid=self.acquisition_authorization_valid,
                repository_scope_authorized=self.repository_scope_authorized,
            ),
            "guardrails": acquisition_guardrails(
                candidate_contents_read=self.candidate_contents_read,
                repository_files_read=self.repository_files_read,
                source_content_acquired=self.source_content_acquired,
            ),
            "payloads_serialized": False,
        }


def render_content_acquisition_result_json(result: ContentAcquisitionResult) -> str:
    if not isinstance(result, ContentAcquisitionResult):
        raise TypeError(
            "render_content_acquisition_result_json requires a ContentAcquisitionResult"
        )
    return json.dumps(result.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)


__all__ = [
    "ACQUISITION_INCONSISTENCIES",
    "ACQUISITION_AUTHORIZATION_REQUIRED",
    "ACQUISITION_AUTHORIZATION_VALIDATED",
    "ACQUISITION_BUDGETS_RESPECTED",
    "ACQUISITION_DIRECT_CONTEXT_REFERENCED",
    "ACQUISITION_EXTERNAL_DISCOVERY_REQUIRED",
    "ACQUISITION_MODES",
    "ACQUISITION_NO_SOURCE_ACQUIRED",
    "ACQUISITION_REASONS",
    "ACQUISITION_REPOSITORY_SOURCES_ACQUIRED",
    "ACQUISITION_RESULT_STATUSES",
    "ACQUISITION_SELECTION_VALIDATED",
    "ACQUISITION_SOURCE_FAILURES_RECORDED",
    "AUTHORIZATION_BOUNDED_REPOSITORY_READ",
    "AUTHORIZATION_EXPLICIT_HUMAN_APPROVAL",
    "AUTHORIZATION_EXISTING_CONTEXT_REFERENCE",
    "AUTHORIZATION_EXTERNAL_DISCOVERY_ACKNOWLEDGED",
    "AUTHORIZATION_REASONS",
    "AUTHORIZATION_SCHEMA_VERSION",
    "AUTHORITY_NOT_VERIFIED",
    "FAILURE_CANDIDATE_MISSING",
    "FAILURE_CANDIDATE_STALE",
    "FAILURE_NON_REGULAR_FILE",
    "FAILURE_PER_SOURCE_BUDGET",
    "FAILURE_READ_ERROR",
    "FAILURE_REQUEST_BYTE_BUDGET",
    "FAILURE_REQUEST_SOURCE_BUDGET",
    "FAILURE_STALE_DURING_ACQUISITION",
    "FAILURE_SYMLINK_REJECTED",
    "FAILURE_TOTAL_BYTE_BUDGET",
    "FAILURE_UNSAFE_PATH",
    "INCONSISTENT_AUTHORIZATION_BINDING",
    "INCONSISTENT_AUTHORIZATION_CANDIDATE",
    "INCONSISTENT_AUTHORIZATION_DOMAIN",
    "INCONSISTENT_AUTHORIZATION_WIDENED",
    "INCONSISTENT_CANDIDATE_RECEIPT",
    "INCONSISTENT_INVENTORY",
    "INCONSISTENT_REPOSITORY_IDENTITY",
    "INCONSISTENT_REPOSITORY_ROOT_INVALID",
    "INCONSISTENT_REPOSITORY_ROOT_REQUIRED",
    "INCONSISTENT_SELECTION_BINDING",
    "INCONSISTENT_SELECTION_BUDGET",
    "INCONSISTENT_SELECTION_DEFERRED",
    "INCONSISTENT_SELECTION_EMPTY",
    "INCONSISTENT_SELECTION_NOT_AUTHORIZED",
    "INCONSISTENT_SELECTION_OUTSIDE_POOL",
    "INCONSISTENT_SELECTOR_ENVELOPE",
    "INCONSISTENT_UPSTREAM_SOURCE",
    "MODE_EXISTING_CONTEXT",
    "MODE_REPOSITORY_READ",
    "PHASE_ID",
    "RESULT_SCHEMA_VERSION",
    "SELECTION_SCHEMA_VERSION",
    "SELECTION_SOURCE_AUTHORIZED_SELECTOR",
    "SELECTION_SOURCE_CTX_SELECT",
    "SELECTION_SOURCE_HUMAN",
    "SELECTION_SOURCES",
    "SOURCE_ACQUIRED",
    "SOURCE_FAILURE_CODES",
    "SOURCE_ALREADY_AVAILABLE_REFERENCE",
    "SOURCE_RECEIPT_SCHEMA_VERSION",
    "STATUS_ACQUIRED",
    "STATUS_AUTHORIZATION_REQUIRED",
    "STATUS_BLOCKED",
    "STATUS_BUDGET_BLOCKED",
    "STATUS_EXTERNAL_DISCOVERY_REQUIRED",
    "STATUS_PARTIAL",
    "STATUS_STALE_CANDIDATES",
    "VERIFICATION_UNVERIFIED",
    "AcquiredSourcePayload",
    "AcquisitionAuthorization",
    "AcquisitionBudgetSummary",
    "AcquisitionSelection",
    "ContentAcquisitionResult",
    "DirectContextReceipt",
    "ExternalDiscoveryRequirement",
    "SourceAcquisitionFailure",
    "SourceAcquisitionReceipt",
    "SourceBinding",
    "acquisition_authority",
    "acquisition_guardrails",
    "authorization_fingerprint",
    "render_content_acquisition_result_json",
    "selection_fingerprint",
]
