"""ACQUIRE.3 — bounded content acquisition and source receipts.

The public operation validates a caller-supplied ACQUIRE.2 subset and a
caller-supplied, human-approved authorization before touching a filesystem.  It
then performs candidate-addressed, read-only, byte-bounded acquisition in the
canonical order required by the selection contract.

It does not choose candidates, execute CTX.SELECT, traverse a repository,
discover replacements, parse content, run validation, plan follow-up work,
write files, contact a network, consult an index/graph/database, call a model,
or promote an acquired source to evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.acquisition_request import (
    ACQUISITION_CONTRACT_SCHEMA_VERSION,
    AcquisitionRequest,
    AcquisitionRequestContract,
)
from core.candidate_eligibility import (
    CANDIDATE_EXPLICIT_TARGET_MATCHED,
    CANDIDATE_INVENTORY_MEMBER,
    CANDIDATE_RECEIPT_SCHEMA_VERSION,
    DESCRIBING_STATUSES,
    EligibleCandidate,
    CandidateEligibilityReceipt,
)
from core.candidate_inventory import (
    CANDIDATE_INVENTORY_SCHEMA_VERSION,
    CandidateInventory,
    InventoryMember,
    is_acceptable_identifier,
)
from core.content_acquisition import (
    ACQUISITION_AUTHORIZATION_REQUIRED,
    ACQUISITION_AUTHORIZATION_VALIDATED,
    ACQUISITION_BUDGETS_RESPECTED,
    ACQUISITION_DIRECT_CONTEXT_REFERENCED,
    ACQUISITION_EXTERNAL_DISCOVERY_REQUIRED,
    ACQUISITION_INCONSISTENCIES,
    ACQUISITION_NO_SOURCE_ACQUIRED,
    ACQUISITION_REASONS,
    ACQUISITION_REPOSITORY_SOURCES_ACQUIRED,
    ACQUISITION_SELECTION_VALIDATED,
    ACQUISITION_SOURCE_FAILURES_RECORDED,
    FAILURE_CANDIDATE_MISSING,
    FAILURE_CANDIDATE_STALE,
    FAILURE_NON_REGULAR_FILE,
    FAILURE_READ_ERROR,
    FAILURE_STALE_DURING_ACQUISITION,
    FAILURE_SYMLINK_REJECTED,
    FAILURE_UNSAFE_PATH,
    INCONSISTENT_AUTHORIZATION_BINDING,
    INCONSISTENT_AUTHORIZATION_CANDIDATE,
    INCONSISTENT_AUTHORIZATION_DOMAIN,
    INCONSISTENT_AUTHORIZATION_WIDENED,
    INCONSISTENT_CANDIDATE_RECEIPT,
    INCONSISTENT_INVENTORY,
    INCONSISTENT_REPOSITORY_IDENTITY,
    INCONSISTENT_REPOSITORY_ROOT_INVALID,
    INCONSISTENT_REPOSITORY_ROOT_REQUIRED,
    INCONSISTENT_SELECTION_BINDING,
    INCONSISTENT_SELECTION_BUDGET,
    INCONSISTENT_SELECTION_DEFERRED,
    INCONSISTENT_SELECTION_EMPTY,
    INCONSISTENT_SELECTION_NOT_AUTHORIZED,
    INCONSISTENT_SELECTION_OUTSIDE_POOL,
    INCONSISTENT_SELECTOR_ENVELOPE,
    INCONSISTENT_UPSTREAM_SOURCE,
    MODE_EXISTING_CONTEXT,
    MODE_REPOSITORY_READ,
    STATUS_ACQUIRED,
    STATUS_AUTHORIZATION_REQUIRED,
    STATUS_BLOCKED,
    STATUS_BUDGET_BLOCKED,
    STATUS_EXTERNAL_DISCOVERY_REQUIRED,
    STATUS_PARTIAL,
    STATUS_STALE_CANDIDATES,
    AcquiredSourcePayload,
    AcquisitionAuthorization,
    AcquisitionBudgetSummary,
    AcquisitionSelection,
    ContentAcquisitionResult,
    DirectContextReceipt,
    ExternalDiscoveryRequirement,
    SourceAcquisitionFailure,
    SourceAcquisitionReceipt,
    SourceBinding,
    authorization_fingerprint,
    selection_fingerprint,
)
from core.eligibility_policy import (
    EligibilityOutcome,
    check_eligibility_monotonicity,
    derive_eligibility,
    validate_selector_output,
)
from core.evidence_candidate_pool import (
    acquisition_contract_identity,
    canonical_eligibility_fingerprint,
)
from core.evidence_requirements import (
    ACTIVE_TIERS,
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
)


PHASE_ID = "ACQUIRE.3"
ACQUISITION_STAGES: tuple[str, ...] = (
    "authorization_presence_gate",
    "upstream_fingerprint_gate",
    "selection_subset_gate",
    "authorization_narrowing_gate",
    "repository_root_gate",
    "selected_candidate_preflight",
    "bounded_read",
    "source_receipt",
)

_FILE_DOMAINS = frozenset({DOMAIN_REPOSITORY, DOMAIN_VALIDATION_ARTIFACTS})
_READ_CHUNK_BYTES = 65_536


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def acquisition_request_fingerprint(contract: AcquisitionRequestContract) -> str:
    """Re-derive the exact ACQUIRE.1 identity ACQUIRE.2 bound."""
    if not isinstance(contract, AcquisitionRequestContract):
        raise TypeError(
            "acquisition_request_fingerprint requires an AcquisitionRequestContract"
        )
    return _fingerprint(acquisition_contract_identity(contract))


def candidate_receipt_fingerprint(receipt: CandidateEligibilityReceipt) -> str:
    """Re-derive a digest over the complete ACQUIRE.2 receipt and bindings."""
    if not isinstance(receipt, CandidateEligibilityReceipt):
        raise TypeError(
            "candidate_receipt_fingerprint requires a CandidateEligibilityReceipt"
        )
    return _fingerprint(canonical_eligibility_fingerprint(receipt))


def _valid_sha256(value: str | None) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _ordered(values: list[str], vocabulary: tuple[str, ...]) -> tuple[str, ...]:
    present = set(values)
    return tuple(item for item in vocabulary if item in present)


def _empty_budget() -> AcquisitionBudgetSummary:
    return AcquisitionBudgetSummary(
        source_limit=0,
        sources_acquired=0,
        total_byte_limit=0,
        bytes_acquired=0,
        max_per_source_bytes=0,
    )


def _safe_digest(value: str | None) -> str | None:
    return value if _valid_sha256(value) else None


def _result_without_reads(
    *,
    status: str,
    acquisition: AcquisitionRequestContract,
    eligibility: CandidateEligibilityReceipt,
    selection: AcquisitionSelection,
    authorization: AcquisitionAuthorization | None,
    reason_codes: list[str],
    inconsistency_codes: list[str] | None = None,
) -> ContentAcquisitionResult:
    request_fingerprint = acquisition_request_fingerprint(acquisition)
    pool_fingerprint = candidate_receipt_fingerprint(eligibility)
    return ContentAcquisitionResult(
        status=status,
        workflow=eligibility.workflow or acquisition.workflow,
        candidate_receipt_fingerprint=pool_fingerprint,
        acquisition_request_fingerprint=request_fingerprint,
        selection_fingerprint=selection_fingerprint(selection),
        authorization_fingerprint=(
            authorization_fingerprint(authorization)
            if authorization is not None
            else None
        ),
        inventory_fingerprint=eligibility.inventory_fingerprint,
        repository_identity=eligibility.repository_identity,
        budget=_empty_budget(),
        task_contract_fingerprint=_safe_digest(
            acquisition.source_contract_fingerprint
        ),
        completion_fingerprint=_safe_digest(
            acquisition.source_completion_fingerprint
        ),
        waiter_decision_fingerprint=_safe_digest(
            acquisition.source_decision_fingerprint
        ),
        evidence_requirement_fingerprint=_safe_digest(
            eligibility.evidence_contract_fingerprint
        ),
        reasons=_ordered(reason_codes, ACQUISITION_REASONS),
        inconsistencies=_ordered(
            inconsistency_codes or [],
            ACQUISITION_INCONSISTENCIES,
        ),
        human_approval_present=(
            authorization.human_approved if authorization is not None else False
        ),
        acquisition_authorization_valid=False,
        repository_scope_authorized=False,
        candidate_contents_read=False,
        repository_files_read=False,
    )


def _eligibility_outcome(receipt: CandidateEligibilityReceipt) -> EligibilityOutcome:
    return EligibilityOutcome(
        active_candidates=receipt.active_candidates,
        secondary_candidates=receipt.secondary_candidates,
        deferred_candidates=receipt.deferred_candidates,
        exclusion_summary=receipt.exclusion_summary,
        selector_envelopes=receipt.selector_envelopes,
        external_envelopes=receipt.external_envelopes,
        unmatched_target_anchors=receipt.unmatched_target_anchors,
        unsatisfied_required_roles=receipt.unsatisfied_required_roles,
        candidate_limit=receipt.candidate_limit,
        source_limit_reserved=receipt.source_limit_reserved,
        byte_limit=receipt.byte_limit,
        byte_eligible_total=receipt.byte_eligible_total,
    )


def _upstream_inconsistencies(
    acquisition: AcquisitionRequestContract,
    eligibility: CandidateEligibilityReceipt,
    request_fingerprint: str,
) -> tuple[str, ...]:
    found: list[str] = []
    if (
        acquisition.schema_version != ACQUISITION_CONTRACT_SCHEMA_VERSION
        or eligibility.schema_version != CANDIDATE_RECEIPT_SCHEMA_VERSION
        or not acquisition.ready
        or eligibility.status not in DESCRIBING_STATUSES
        or acquisition.workflow != eligibility.workflow
        or acquisition.evidence_scope != eligibility.evidence_scope
        or eligibility.acquisition_request_fingerprint != request_fingerprint
        or eligibility.evidence_contract_fingerprint
        != acquisition.source_evidence_fingerprint
        or check_eligibility_monotonicity(
            _eligibility_outcome(eligibility), acquisition
        )
    ):
        found.append(INCONSISTENT_UPSTREAM_SOURCE)
    for value in (
        acquisition.source_contract_fingerprint,
        acquisition.source_completion_fingerprint,
        acquisition.source_decision_fingerprint,
        acquisition.source_evidence_fingerprint,
        eligibility.evidence_contract_fingerprint,
        eligibility.acquisition_request_fingerprint,
    ):
        if not _valid_sha256(value):
            found.append(INCONSISTENT_UPSTREAM_SOURCE)
            break
    return tuple(dict.fromkeys(found))


def _candidate_maps(
    eligibility: CandidateEligibilityReceipt,
) -> tuple[dict[str, EligibleCandidate], dict[str, EligibleCandidate]]:
    active = {
        candidate.identifier: candidate
        for candidate in eligibility.active_candidates
        + eligibility.secondary_candidates
    }
    deferred = {
        candidate.identifier: candidate
        for candidate in eligibility.deferred_candidates
    }
    return active, deferred


def _validate_selection(
    acquisition: AcquisitionRequestContract,
    eligibility: CandidateEligibilityReceipt,
    selection: AcquisitionSelection,
    *,
    request_fingerprint: str,
    pool_fingerprint: str,
) -> tuple[dict[str, EligibleCandidate], tuple[str, ...]]:
    found: list[str] = []
    if (
        selection.candidate_receipt_fingerprint != pool_fingerprint
        or selection.acquisition_request_fingerprint != request_fingerprint
        or selection.inventory_fingerprint != eligibility.inventory_fingerprint
        or selection.repository_identity != eligibility.repository_identity
    ):
        found.append(INCONSISTENT_SELECTION_BINDING)

    active, deferred = _candidate_maps(eligibility)
    selected: dict[str, EligibleCandidate] = {}
    for identifier in selection.candidate_identifiers:
        candidate = active.get(identifier)
        if candidate is None:
            if identifier in deferred:
                found.append(INCONSISTENT_SELECTION_DEFERRED)
            else:
                found.append(INCONSISTENT_SELECTION_OUTSIDE_POOL)
            continue
        selected[identifier] = candidate
        request = acquisition.request_for(candidate.domain, candidate.tier)
        if request is None or candidate.tier not in ACTIVE_TIERS:
            found.append(INCONSISTENT_SELECTION_OUTSIDE_POOL)
            continue
        if candidate.domain not in _FILE_DOMAINS | {DOMAIN_DIRECT_CONTEXT}:
            # ACQUIRE.3 has exactly two concrete acquisition modes. A forged
            # active historical (or future-domain) candidate must be refused,
            # never silently skipped by the bounded read loop.
            found.append(INCONSISTENT_SELECTION_OUTSIDE_POOL)
            continue
        if not set(candidate.eligible_roles) <= set(request.required_roles):
            found.append(INCONSISTENT_SELECTION_OUTSIDE_POOL)
        if not set(candidate.eligible_source_classes) <= set(request.source_classes):
            found.append(INCONSISTENT_SELECTION_OUTSIDE_POOL)
        if not candidate.eligible_roles and not candidate.eligible_source_classes:
            if not (
                candidate.target_anchor_match
                and CANDIDATE_EXPLICIT_TARGET_MATCHED in candidate.reasons
                and CANDIDATE_INVENTORY_MEMBER in candidate.reasons
            ):
                found.append(INCONSISTENT_SELECTION_OUTSIDE_POOL)

    if len(selection.candidate_identifiers) > eligibility.source_limit_reserved:
        found.append(INCONSISTENT_SELECTION_BUDGET)

    # Use ACQUIRE.2's selector-envelope validator for every file-domain group.
    # Passing no inventory here avoids reclassifying the explicit roleless
    # target without its anchor fact; inventory identity is checked separately.
    grouped: dict[tuple[str, str], list[str]] = {}
    for identifier in selection.candidate_identifiers:
        candidate = selected.get(identifier)
        if candidate is not None and candidate.domain in _FILE_DOMAINS:
            grouped.setdefault((candidate.domain, candidate.tier), []).append(identifier)
    for key, identifiers in grouped.items():
        envelope = eligibility.envelope_for(*key)
        if envelope is None:
            found.append(INCONSISTENT_SELECTOR_ENVELOPE)
            continue
        if (
            envelope.acquisition_request_fingerprint
            != acquisition.source_evidence_fingerprint
            or envelope.inventory_fingerprint != eligibility.inventory_fingerprint
            or envelope.repository_identity != eligibility.repository_identity
            or len(identifiers) > envelope.source_budget_reserved
            or validate_selector_output(envelope, tuple(identifiers))
        ):
            found.append(INCONSISTENT_SELECTOR_ENVELOPE)

    if (
        not selection.candidate_identifiers
        and not eligibility.external_envelopes
    ):
        found.append(INCONSISTENT_SELECTION_EMPTY)
    return selected, tuple(dict.fromkeys(found))


def _validate_inventory(
    acquisition: AcquisitionRequestContract,
    eligibility: CandidateEligibilityReceipt,
    selection: AcquisitionSelection,
    selected: dict[str, EligibleCandidate],
    inventory: CandidateInventory | None,
) -> tuple[dict[str, InventoryMember], tuple[str, ...]]:
    file_identifiers = [
        identifier
        for identifier in selection.candidate_identifiers
        if identifier in selected and selected[identifier].domain in _FILE_DOMAINS
    ]
    found: list[str] = []
    inventory_expected = eligibility.inventory_fingerprint is not None
    if inventory_expected and inventory is None:
        return {}, (INCONSISTENT_INVENTORY,)
    if file_identifiers and not inventory_expected:
        return {}, (INCONSISTENT_INVENTORY,)
    if inventory_expected:
        assert inventory is not None
        if (
            inventory.schema_version != CANDIDATE_INVENTORY_SCHEMA_VERSION
            or not inventory.declared_fingerprint_matches()
            or inventory.fingerprint() != eligibility.inventory_fingerprint
        ):
            found.append(INCONSISTENT_INVENTORY)
        if inventory.repository_identity != eligibility.repository_identity:
            found.append(INCONSISTENT_REPOSITORY_IDENTITY)

    # The fingerprint identifies the supplied metadata snapshot. Re-deriving
    # ACQUIRE.2's metadata-only outcome proves that the snapshot still yields
    # this exact envelope. A forged receipt therefore cannot re-admit a hard
    # exclusion, generated/duplicate/snapshot material, an outside member, or a
    # declared symlink escape.
    try:
        rederived = derive_eligibility(
            acquisition, inventory if inventory_expected else None
        )
    except (TypeError, ValueError):
        found.append(INCONSISTENT_CANDIDATE_RECEIPT)
    else:
        if (
            rederived.active_candidates != eligibility.active_candidates
            or rederived.secondary_candidates != eligibility.secondary_candidates
            or rederived.deferred_candidates != eligibility.deferred_candidates
            or rederived.exclusion_summary != eligibility.exclusion_summary
            or rederived.selector_envelopes != eligibility.selector_envelopes
            or rederived.external_envelopes != eligibility.external_envelopes
            or rederived.unmatched_target_anchors
            != eligibility.unmatched_target_anchors
            or rederived.unsatisfied_required_roles
            != eligibility.unsatisfied_required_roles
            or rederived.candidate_limit != eligibility.candidate_limit
            or rederived.source_limit_reserved != eligibility.source_limit_reserved
            or rederived.byte_limit != eligibility.byte_limit
            or rederived.byte_eligible_total != eligibility.byte_eligible_total
        ):
            found.append(INCONSISTENT_CANDIDATE_RECEIPT)

    members: dict[str, InventoryMember] = {}
    if inventory is None:
        return members, tuple(dict.fromkeys(found))
    for identifier in file_identifiers:
        member = inventory.member(identifier)
        candidate = selected[identifier]
        if (
            member is None
            or member.identifier != identifier
            or not is_acceptable_identifier(identifier)
            or member.size_bytes != candidate.size_bytes
        ):
            found.append(INCONSISTENT_INVENTORY)
            continue
        members[identifier] = member
    return members, tuple(dict.fromkeys(found))


def _grant_requests(
    acquisition: AcquisitionRequestContract,
    authorization: AcquisitionAuthorization,
) -> tuple[AcquisitionRequest, ...]:
    domains = set(authorization.allowed_domains)
    return tuple(
        request
        for request in acquisition.requests
        if request.domain in domains and request.tier in ACTIVE_TIERS
    )


def _validate_authorization(
    acquisition: AcquisitionRequestContract,
    eligibility: CandidateEligibilityReceipt,
    selection: AcquisitionSelection,
    authorization: AcquisitionAuthorization,
    selected: dict[str, EligibleCandidate],
    *,
    request_fingerprint: str,
    pool_fingerprint: str,
) -> tuple[str, ...]:
    found: list[str] = []
    if (
        authorization.candidate_pool_fingerprint != pool_fingerprint
        or authorization.acquisition_request_fingerprint != request_fingerprint
        or authorization.inventory_fingerprint != eligibility.inventory_fingerprint
        or authorization.repository_identity != eligibility.repository_identity
    ):
        found.append(INCONSISTENT_AUTHORIZATION_BINDING)

    active, _ = _candidate_maps(eligibility)
    authorized: dict[str, EligibleCandidate] = {}
    for identifier in authorization.allowed_candidate_identifiers:
        candidate = active.get(identifier)
        if candidate is None:
            found.append(INCONSISTENT_AUTHORIZATION_CANDIDATE)
        else:
            authorized[identifier] = candidate

    available_domains = {candidate.domain for candidate in active.values()}
    if eligibility.external_envelopes:
        available_domains.add(DOMAIN_EXTERNAL_INFORMATION)
    if not set(authorization.allowed_domains) <= available_domains:
        found.append(INCONSISTENT_AUTHORIZATION_DOMAIN)
    if any(
        candidate.domain not in set(authorization.allowed_domains)
        for candidate in authorized.values()
    ):
        found.append(INCONSISTENT_AUTHORIZATION_DOMAIN)

    if not set(selection.candidate_identifiers) <= set(
        authorization.allowed_candidate_identifiers
    ) or any(
        candidate.domain not in set(authorization.allowed_domains)
        for candidate in selected.values()
    ):
        found.append(INCONSISTENT_SELECTION_NOT_AUTHORIZED)

    requests = _grant_requests(acquisition, authorization)
    source_ceiling = sum(request.budget.max_initial_sources for request in requests)
    file_requests = tuple(
        request for request in requests if request.domain in _FILE_DOMAINS
    )
    byte_ceiling = sum(request.budget.max_total_bytes for request in file_requests)
    per_source_ceiling = max(
        (request.budget.max_per_source_bytes for request in file_requests),
        default=0,
    )
    if (
        authorization.max_sources
        > min(eligibility.source_limit_reserved, source_ceiling)
        or authorization.max_total_bytes
        > min(eligibility.byte_limit, byte_ceiling)
        or authorization.max_per_source_bytes > per_source_ceiling
    ):
        found.append(INCONSISTENT_AUTHORIZATION_WIDENED)

    authorized_file_candidates = tuple(
        candidate
        for candidate in authorized.values()
        if candidate.domain in _FILE_DOMAINS
    )
    if any(candidate.size_bytes is None for candidate in authorized_file_candidates):
        found.append(INCONSISTENT_AUTHORIZATION_CANDIDATE)

    # The allowlist is an envelope, not a spending declaration. Its cardinality
    # and aggregate metadata may exceed the grant's source/byte caps; the closed
    # explicit selection below is what spends those caps. Every allowed concrete
    # file must nevertheless still fit its own ACQUIRE.1 request.
    for candidate in authorized_file_candidates:
        request = acquisition.request_for(candidate.domain, candidate.tier)
        if (
            request is None
            or candidate.size_bytes is None
            or candidate.size_bytes > request.budget.max_per_source_bytes
        ):
            found.append(INCONSISTENT_AUTHORIZATION_CANDIDATE)

    if len(selection.candidate_identifiers) > authorization.max_sources:
        found.append(INCONSISTENT_SELECTION_BUDGET)
    selected_file_candidates = [
        candidate
        for identifier, candidate in selected.items()
        if identifier in set(selection.candidate_identifiers)
        and candidate.domain in _FILE_DOMAINS
    ]
    selected_sizes = [candidate.size_bytes for candidate in selected_file_candidates]
    if any(size is None for size in selected_sizes):
        found.append(INCONSISTENT_SELECTION_BUDGET)
    else:
        exact_selected_sizes = [int(size) for size in selected_sizes]
        if any(
            size > authorization.max_per_source_bytes
            for size in exact_selected_sizes
        ) or sum(exact_selected_sizes) > authorization.max_total_bytes:
            found.append(INCONSISTENT_SELECTION_BUDGET)

    # The global authorization cannot lend one request another request's budget.
    for request in acquisition.requests:
        request_candidates = [
            candidate
            for candidate in selected_file_candidates
            if (candidate.domain, candidate.tier) == request.key
        ]
        if len(request_candidates) > request.budget.max_initial_sources:
            found.append(INCONSISTENT_SELECTION_BUDGET)
        sizes = [candidate.size_bytes or 0 for candidate in request_candidates]
        if (
            sum(sizes) > request.budget.max_total_bytes
            or any(size > request.budget.max_per_source_bytes for size in sizes)
        ):
            found.append(INCONSISTENT_SELECTION_BUDGET)
    return tuple(dict.fromkeys(found))


def _candidate_lstat(path: Path) -> os.stat_result:
    return os.lstat(path)


def _descriptor_fstat(descriptor: int) -> os.stat_result:
    return os.fstat(descriptor)


def _descriptor_read(descriptor: int, count: int) -> bytes:
    return os.read(descriptor, count)


def _open_readonly(path: Path) -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    return os.open(path, flags)


def _is_reparse_or_symlink(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0) or 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(attributes & reparse_flag) or bool(
        int(getattr(metadata, "st_reparse_tag", 0) or 0)
    )


def _stat_signature(
    metadata: os.stat_result,
) -> tuple[int, int, int, int, int, int, int]:
    changed_ns = int(getattr(metadata, "st_ctime_ns", 0) or 0)
    created_ns = int(getattr(metadata, "st_birthtime_ns", 0) or 0)
    return (
        int(getattr(metadata, "st_dev", 0) or 0),
        int(getattr(metadata, "st_ino", 0) or 0),
        int(metadata.st_mode),
        int(metadata.st_size),
        int(
            getattr(
                metadata,
                "st_mtime_ns",
                int(metadata.st_mtime * 1_000_000_000),
            )
            or 0
        ),
        0 if os.name == "nt" else changed_ns,
        created_ns if os.name == "nt" else 0,
    )


@dataclass(frozen=True, slots=True)
class _AuthorizedRoot:
    path: Path
    metadata: os.stat_result


def _resolve_authorized_root(root_value: str | None) -> _AuthorizedRoot | None:
    if root_value is None:
        return None
    if root_value.startswith(("\\\\", "//")):
        return None
    try:
        root = Path(root_value)
        if not root.is_absolute():
            return None
        raw_metadata = _candidate_lstat(root)
        if _is_reparse_or_symlink(raw_metadata) or not stat.S_ISDIR(
            raw_metadata.st_mode
        ):
            return None
        resolved = root.resolve(strict=True)
        resolved_metadata = _candidate_lstat(resolved)
        raw_absolute = os.path.normcase(os.path.abspath(os.fspath(root)))
        resolved_absolute = os.path.normcase(os.path.abspath(os.fspath(resolved)))
    except (OSError, RuntimeError, ValueError, UnicodeError):
        return None
    if raw_absolute != resolved_absolute:
        return None
    if _stat_signature(raw_metadata) != _stat_signature(resolved_metadata):
        return None
    return _AuthorizedRoot(path=resolved, metadata=resolved_metadata)


def _authorized_root_is_stable(root: _AuthorizedRoot) -> bool:
    try:
        current = _candidate_lstat(root.path)
        if _is_reparse_or_symlink(current) or not stat.S_ISDIR(current.st_mode):
            return False
        resolved = root.path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError, UnicodeError):
        return False
    return (
        os.path.normcase(os.path.abspath(os.fspath(resolved)))
        == os.path.normcase(os.path.abspath(os.fspath(root.path)))
        and _stat_signature(current) == _stat_signature(root.metadata)
    )


@dataclass(frozen=True, slots=True)
class _PreparedSource:
    candidate: EligibleCandidate
    member: InventoryMember
    request: AcquisitionRequest
    path: Path
    metadata: os.stat_result


def _inspect_selected_path(
    root: Path,
    member: InventoryMember,
) -> tuple[Path | None, os.stat_result | None, str | None]:
    if not is_acceptable_identifier(member.identifier):
        return None, None, FAILURE_UNSAFE_PATH
    current = root
    parts = tuple(member.identifier.split("/"))
    try:
        for index, part in enumerate(parts):
            current = current / part
            metadata = _candidate_lstat(current)
            if _is_reparse_or_symlink(metadata):
                return None, None, FAILURE_SYMLINK_REJECTED
            if index < len(parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
                return None, None, FAILURE_NON_REGULAR_FILE
        resolved = current.resolve(strict=True)
        common = os.path.commonpath((os.fspath(root), os.fspath(resolved)))
        if os.path.normcase(common) != os.path.normcase(os.fspath(root)):
            return None, None, FAILURE_UNSAFE_PATH
        if not stat.S_ISREG(metadata.st_mode):
            return None, None, FAILURE_NON_REGULAR_FILE
    except FileNotFoundError:
        return None, None, FAILURE_CANDIDATE_MISSING
    except (OSError, RuntimeError, ValueError):
        return None, None, FAILURE_UNSAFE_PATH
    return resolved, metadata, None


def _preflight_source(
    root: Path,
    candidate: EligibleCandidate,
    member: InventoryMember,
    request: AcquisitionRequest,
) -> tuple[_PreparedSource | None, SourceAcquisitionFailure | None]:
    path, metadata, failure = _inspect_selected_path(root, member)
    if failure is not None:
        return None, SourceAcquisitionFailure(
            candidate_identifier=candidate.identifier,
            domain=candidate.domain,
            tier=candidate.tier,
            failure_code=failure,
            expected_size_bytes=candidate.size_bytes,
        )
    assert path is not None and metadata is not None
    if (
        candidate.size_bytes is None
        or member.size_bytes is None
        or metadata.st_size != candidate.size_bytes
        or metadata.st_size != member.size_bytes
    ):
        return None, SourceAcquisitionFailure(
            candidate_identifier=candidate.identifier,
            domain=candidate.domain,
            tier=candidate.tier,
            failure_code=FAILURE_CANDIDATE_STALE,
            expected_size_bytes=candidate.size_bytes,
        )
    return (
        _PreparedSource(
            candidate=candidate,
            member=member,
            request=request,
            path=path,
            metadata=metadata,
        ),
        None,
    )


def _read_exact(descriptor: int, expected: int) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    remaining = expected
    try:
        while remaining:
            chunk = _descriptor_read(descriptor, min(_READ_CHUNK_BYTES, remaining))
            if not chunk:
                return b"".join(chunks), False
            if len(chunk) > remaining:
                return b"".join(chunks), False
            chunks.append(chunk)
            remaining -= len(chunk)
    except OSError:
        return b"".join(chunks), False
    return b"".join(chunks), True


def _source_binding(
    *,
    acquisition: AcquisitionRequestContract,
    eligibility: CandidateEligibilityReceipt,
    candidate_identifier: str,
    mode: str,
    request_fingerprint: str,
    pool_fingerprint: str,
    selection_digest: str,
    authorization_digest: str,
) -> SourceBinding:
    return SourceBinding(
        candidate_identifier=candidate_identifier,
        acquisition_mode=mode,
        task_contract_fingerprint=acquisition.source_contract_fingerprint or "",
        completion_fingerprint=acquisition.source_completion_fingerprint or "",
        waiter_decision_fingerprint=acquisition.source_decision_fingerprint or "",
        evidence_requirement_fingerprint=(
            eligibility.evidence_contract_fingerprint or ""
        ),
        acquisition_request_fingerprint=request_fingerprint,
        candidate_receipt_fingerprint=pool_fingerprint,
        selection_fingerprint=selection_digest,
        authorization_fingerprint=authorization_digest,
        inventory_fingerprint=(
            eligibility.inventory_fingerprint
            if mode == MODE_REPOSITORY_READ
            else None
        ),
        repository_identity=(
            eligibility.repository_identity if mode == MODE_REPOSITORY_READ else None
        ),
    )


def _acquire_prepared_source(
    prepared: _PreparedSource,
    *,
    root: _AuthorizedRoot,
    binding: SourceBinding,
) -> tuple[
    AcquiredSourcePayload | None,
    SourceAcquisitionReceipt | None,
    SourceAcquisitionFailure | None,
    int,
    bool,
]:
    candidate = prepared.candidate
    expected = int(candidate.size_bytes or 0)
    descriptor: int | None = None
    data = b""
    read_attempted = False
    try:
        if not _authorized_root_is_stable(root):
            return (
                None,
                None,
                SourceAcquisitionFailure(
                    candidate_identifier=candidate.identifier,
                    domain=candidate.domain,
                    tier=candidate.tier,
                    failure_code=FAILURE_UNSAFE_PATH,
                    expected_size_bytes=candidate.size_bytes,
                ),
                0,
                False,
            )
        preopen_path, preopen_metadata, preopen_failure = _inspect_selected_path(
            root.path, prepared.member
        )
        if (
            preopen_failure is not None
            or preopen_path != prepared.path
            or preopen_metadata is None
            or _stat_signature(preopen_metadata)
            != _stat_signature(prepared.metadata)
        ):
            failure_code = (
                preopen_failure
                if preopen_failure is not None
                else FAILURE_STALE_DURING_ACQUISITION
            )
            return (
                None,
                None,
                SourceAcquisitionFailure(
                    candidate_identifier=candidate.identifier,
                    domain=candidate.domain,
                    tier=candidate.tier,
                    failure_code=failure_code,
                    expected_size_bytes=candidate.size_bytes,
                ),
                0,
                False,
            )
        descriptor = _open_readonly(prepared.path)
        opened = _descriptor_fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or _is_reparse_or_symlink(opened)
            or _stat_signature(opened) != _stat_signature(prepared.metadata)
        ):
            return (
                None,
                None,
                SourceAcquisitionFailure(
                    candidate_identifier=candidate.identifier,
                    domain=candidate.domain,
                    tier=candidate.tier,
                    failure_code=FAILURE_STALE_DURING_ACQUISITION,
                    expected_size_bytes=candidate.size_bytes,
                ),
                0,
                False,
            )
        read_attempted = True
        data, complete = _read_exact(descriptor, expected)
        final_descriptor = _descriptor_fstat(descriptor)
        post_path, post_metadata, post_failure = _inspect_selected_path(
            root.path, prepared.member
        )
        stable = (
            complete
            and len(data) == expected
            and post_failure is None
            and post_path == prepared.path
            and post_metadata is not None
            and _stat_signature(final_descriptor) == _stat_signature(opened)
            and _stat_signature(post_metadata) == _stat_signature(opened)
            and _authorized_root_is_stable(root)
        )
        if not stable:
            failure_code = (
                FAILURE_READ_ERROR
                if not complete and len(data) < expected
                else FAILURE_STALE_DURING_ACQUISITION
            )
            return (
                None,
                None,
                SourceAcquisitionFailure(
                    candidate_identifier=candidate.identifier,
                    domain=candidate.domain,
                    tier=candidate.tier,
                    failure_code=failure_code,
                    expected_size_bytes=candidate.size_bytes,
                ),
                len(data),
                read_attempted,
            )
    except OSError:
        return (
            None,
            None,
            SourceAcquisitionFailure(
                candidate_identifier=candidate.identifier,
                domain=candidate.domain,
                tier=candidate.tier,
                failure_code=FAILURE_READ_ERROR,
                expected_size_bytes=candidate.size_bytes,
            ),
            len(data),
            read_attempted,
        )
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                # Keep descriptor-cleanup failures inside the bounded API; they
                # must not replace the already-determined per-source outcome.
                pass

    digest = hashlib.sha256(data).hexdigest()
    payload = AcquiredSourcePayload(
        candidate_identifier=candidate.identifier,
        content=data,
        content_sha256=digest,
        bytes_acquired=len(data),
        source_binding=binding,
    )
    receipt = SourceAcquisitionReceipt(
        candidate_identifier=candidate.identifier,
        domain=candidate.domain,
        tier=candidate.tier,
        expected_roles=candidate.eligible_roles,
        eligible_source_classes=candidate.eligible_source_classes,
        target_artifact=candidate.target_anchor_match,
        content_sha256=digest,
        bytes_acquired=len(data),
        source_binding=binding,
    )
    return payload, receipt, None, len(data), True


def acquire_selected_content(
    acquisition: AcquisitionRequestContract,
    eligibility: CandidateEligibilityReceipt,
    selection: AcquisitionSelection,
    authorization: AcquisitionAuthorization | None = None,
    *,
    inventory: CandidateInventory | None = None,
) -> ContentAcquisitionResult:
    """Acquire only a supplied, authorized ACQUIRE.2 subset.

    Absence of authorization, ``acquisition_allowed=False`` or
    ``human_approved=False`` returns ``authorization_required`` before any
    inventory path, repository root or candidate path is touched.
    """
    if not isinstance(acquisition, AcquisitionRequestContract):
        raise TypeError("acquire_selected_content requires an AcquisitionRequestContract")
    if not isinstance(eligibility, CandidateEligibilityReceipt):
        raise TypeError("acquire_selected_content requires a CandidateEligibilityReceipt")
    if not isinstance(selection, AcquisitionSelection):
        raise TypeError("acquire_selected_content requires an AcquisitionSelection")
    if authorization is not None and not isinstance(
        authorization, AcquisitionAuthorization
    ):
        raise TypeError(
            "acquire_selected_content requires an AcquisitionAuthorization or None"
        )
    if inventory is not None and not isinstance(inventory, CandidateInventory):
        raise TypeError("inventory must be a CandidateInventory or None")

    if (
        authorization is None
        or not authorization.acquisition_allowed
        or not authorization.human_approved
    ):
        return _result_without_reads(
            status=STATUS_AUTHORIZATION_REQUIRED,
            acquisition=acquisition,
            eligibility=eligibility,
            selection=selection,
            authorization=authorization,
            reason_codes=[ACQUISITION_AUTHORIZATION_REQUIRED],
        )

    request_fingerprint = acquisition_request_fingerprint(acquisition)
    pool_fingerprint = candidate_receipt_fingerprint(eligibility)
    selection_digest = selection_fingerprint(selection)
    authorization_digest = authorization_fingerprint(authorization)

    upstream_errors = _upstream_inconsistencies(
        acquisition, eligibility, request_fingerprint
    )
    if upstream_errors:
        return _result_without_reads(
            status=STATUS_BLOCKED,
            acquisition=acquisition,
            eligibility=eligibility,
            selection=selection,
            authorization=authorization,
            reason_codes=[ACQUISITION_NO_SOURCE_ACQUIRED],
            inconsistency_codes=list(upstream_errors),
        )

    selected, selection_errors = _validate_selection(
        acquisition,
        eligibility,
        selection,
        request_fingerprint=request_fingerprint,
        pool_fingerprint=pool_fingerprint,
    )
    if selection_errors:
        status = (
            STATUS_BUDGET_BLOCKED
            if INCONSISTENT_SELECTION_BUDGET in selection_errors
            else STATUS_BLOCKED
        )
        return _result_without_reads(
            status=status,
            acquisition=acquisition,
            eligibility=eligibility,
            selection=selection,
            authorization=authorization,
            reason_codes=[ACQUISITION_NO_SOURCE_ACQUIRED],
            inconsistency_codes=list(selection_errors),
        )

    members, inventory_errors = _validate_inventory(
        acquisition, eligibility, selection, selected, inventory
    )
    if inventory_errors:
        return _result_without_reads(
            status=STATUS_BLOCKED,
            acquisition=acquisition,
            eligibility=eligibility,
            selection=selection,
            authorization=authorization,
            reason_codes=[ACQUISITION_NO_SOURCE_ACQUIRED],
            inconsistency_codes=list(inventory_errors),
        )

    authorization_errors = _validate_authorization(
        acquisition,
        eligibility,
        selection,
        authorization,
        selected,
        request_fingerprint=request_fingerprint,
        pool_fingerprint=pool_fingerprint,
    )
    if authorization_errors:
        status = (
            STATUS_BUDGET_BLOCKED
            if any(
                item
                in {
                    INCONSISTENT_AUTHORIZATION_WIDENED,
                    INCONSISTENT_SELECTION_BUDGET,
                }
                for item in authorization_errors
            )
            else STATUS_BLOCKED
        )
        return _result_without_reads(
            status=status,
            acquisition=acquisition,
            eligibility=eligibility,
            selection=selection,
            authorization=authorization,
            reason_codes=[ACQUISITION_NO_SOURCE_ACQUIRED],
            inconsistency_codes=list(authorization_errors),
        )

    repository_selection = [
        candidate
        for identifier, candidate in selected.items()
        if identifier in set(selection.candidate_identifiers)
        and candidate.domain in _FILE_DOMAINS
    ]
    root: _AuthorizedRoot | None = None
    if repository_selection:
        if authorization.repository_root is None:
            return _result_without_reads(
                status=STATUS_BLOCKED,
                acquisition=acquisition,
                eligibility=eligibility,
                selection=selection,
                authorization=authorization,
                reason_codes=[ACQUISITION_NO_SOURCE_ACQUIRED],
                inconsistency_codes=[INCONSISTENT_REPOSITORY_ROOT_REQUIRED],
            )
        root = _resolve_authorized_root(authorization.repository_root)
        if root is None:
            return _result_without_reads(
                status=STATUS_BLOCKED,
                acquisition=acquisition,
                eligibility=eligibility,
                selection=selection,
                authorization=authorization,
                reason_codes=[ACQUISITION_NO_SOURCE_ACQUIRED],
                inconsistency_codes=[INCONSISTENT_REPOSITORY_ROOT_INVALID],
            )

    # Every pure gate and the root gate has passed.  Only selected candidates are
    # touched below, first by preflight and then by bounded read.
    prepared: dict[str, _PreparedSource] = {}
    failures: list[SourceAcquisitionFailure] = []
    if root is not None:
        for identifier in selection.candidate_identifiers:
            candidate = selected.get(identifier)
            if candidate is None or candidate.domain not in _FILE_DOMAINS:
                continue
            request = acquisition.request_for(candidate.domain, candidate.tier)
            assert request is not None
            ready, failure = _preflight_source(
                root.path, candidate, members[identifier], request
            )
            if failure is not None:
                failures.append(failure)
            else:
                assert ready is not None
                prepared[identifier] = ready

    payloads: list[AcquiredSourcePayload] = []
    receipts: list[SourceAcquisitionReceipt] = []
    direct_receipts: list[DirectContextReceipt] = []
    bytes_read = 0
    any_content_read = False

    for identifier in selection.candidate_identifiers:
        candidate = selected[identifier]
        if candidate.domain == DOMAIN_DIRECT_CONTEXT:
            binding = _source_binding(
                acquisition=acquisition,
                eligibility=eligibility,
                candidate_identifier=identifier,
                mode=MODE_EXISTING_CONTEXT,
                request_fingerprint=request_fingerprint,
                pool_fingerprint=pool_fingerprint,
                selection_digest=selection_digest,
                authorization_digest=authorization_digest,
            )
            direct_receipts.append(
                DirectContextReceipt(
                    candidate_identifier=identifier,
                    tier=candidate.tier,
                    expected_roles=candidate.eligible_roles,
                    eligible_source_classes=candidate.eligible_source_classes,
                    source_binding=binding,
                )
            )
            continue
        if candidate.domain not in _FILE_DOMAINS or identifier not in prepared:
            continue
        binding = _source_binding(
            acquisition=acquisition,
            eligibility=eligibility,
            candidate_identifier=identifier,
            mode=MODE_REPOSITORY_READ,
            request_fingerprint=request_fingerprint,
            pool_fingerprint=pool_fingerprint,
            selection_digest=selection_digest,
            authorization_digest=authorization_digest,
        )
        payload, receipt, failure, physical_bytes, read_performed = (
            _acquire_prepared_source(prepared[identifier], root=root, binding=binding)
        )
        bytes_read += physical_bytes
        any_content_read = any_content_read or read_performed
        if failure is not None:
            failures.append(failure)
        else:
            assert payload is not None and receipt is not None
            payloads.append(payload)
            receipts.append(receipt)

    unresolved_external = tuple(
        ExternalDiscoveryRequirement(
            required_role=envelope.required_role,
            allowed_source_classes=envelope.allowed_source_classes,
            freshness=envelope.freshness,
            candidate_budget=envelope.candidate_budget,
            source_budget_reserved=envelope.source_budget_reserved,
        )
        for envelope in eligibility.external_envelopes
    )

    success = bool(receipts or direct_receipts)
    unresolved = bool(failures or unresolved_external)
    if success:
        status = STATUS_PARTIAL if unresolved else STATUS_ACQUIRED
    elif unresolved_external and not failures:
        status = STATUS_EXTERNAL_DISCOVERY_REQUIRED
    elif failures and not unresolved_external and all(
        item.failure_code
        in {
            FAILURE_CANDIDATE_MISSING,
            FAILURE_CANDIDATE_STALE,
            FAILURE_STALE_DURING_ACQUISITION,
        }
        for item in failures
    ):
        status = STATUS_STALE_CANDIDATES
    else:
        status = STATUS_BLOCKED

    reason_codes = [
        ACQUISITION_AUTHORIZATION_VALIDATED,
        ACQUISITION_SELECTION_VALIDATED,
        ACQUISITION_BUDGETS_RESPECTED,
    ]
    if receipts:
        reason_codes.append(ACQUISITION_REPOSITORY_SOURCES_ACQUIRED)
    if direct_receipts:
        reason_codes.append(ACQUISITION_DIRECT_CONTEXT_REFERENCED)
    if unresolved_external:
        reason_codes.append(ACQUISITION_EXTERNAL_DISCOVERY_REQUIRED)
    if failures:
        reason_codes.append(ACQUISITION_SOURCE_FAILURES_RECORDED)
    if not success:
        reason_codes.append(ACQUISITION_NO_SOURCE_ACQUIRED)

    selected_file_sizes = [
        int(candidate.size_bytes or 0) for candidate in repository_selection
    ]
    budget = AcquisitionBudgetSummary(
        source_limit=authorization.max_sources,
        sources_acquired=len(receipts) + len(direct_receipts),
        total_byte_limit=authorization.max_total_bytes,
        bytes_acquired=sum(item.bytes_acquired for item in receipts),
        max_per_source_bytes=authorization.max_per_source_bytes,
        sources_selected=len(selection.candidate_identifiers),
        bytes_selected_reserved=sum(selected_file_sizes),
        bytes_read=bytes_read,
    )
    return ContentAcquisitionResult(
        status=status,
        workflow=eligibility.workflow,
        candidate_receipt_fingerprint=pool_fingerprint,
        acquisition_request_fingerprint=request_fingerprint,
        selection_fingerprint=selection_digest,
        authorization_fingerprint=authorization_digest,
        inventory_fingerprint=eligibility.inventory_fingerprint,
        repository_identity=eligibility.repository_identity,
        budget=budget,
        task_contract_fingerprint=acquisition.source_contract_fingerprint,
        completion_fingerprint=acquisition.source_completion_fingerprint,
        waiter_decision_fingerprint=acquisition.source_decision_fingerprint,
        evidence_requirement_fingerprint=eligibility.evidence_contract_fingerprint,
        payloads=tuple(payloads),
        acquired_receipts=tuple(receipts),
        failed_receipts=tuple(failures),
        direct_context_receipts=tuple(direct_receipts),
        unresolved_external_requests=unresolved_external,
        reasons=_ordered(reason_codes, ACQUISITION_REASONS),
        human_approval_present=True,
        acquisition_authorization_valid=True,
        repository_scope_authorized=bool(repository_selection),
        candidate_contents_read=any_content_read,
        repository_files_read=any_content_read,
    )


__all__ = [
    "ACQUISITION_STAGES",
    "PHASE_ID",
    "acquire_selected_content",
    "acquisition_request_fingerprint",
    "candidate_receipt_fingerprint",
]
