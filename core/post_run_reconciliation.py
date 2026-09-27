"""CHECK.1 — Post-Run Contract Reconciliation.

This module owns one deliberately narrow transition::

    execution authorization
        + worker self-report
        + objective observed change facts
        + validation expectations / receipts
        + execution state bindings
        -> PostRunReconciliation

It answers exactly one question::

    "Did the execution remain inside the contract it was given, and does its
     self-report agree with what objectively happened?"

It does **not** answer::

    "Was the implementation semantically good / does it satisfy the goal?"

That belongs to a future CHECK.2 semantic goal-fidelity review, which this
module deliberately does not implement.  Every result — including a fully
``reconciled`` one — states that semantic goal review is still required.

Three invariants make the reconciliation trustworthy:

1. Objective observed change facts outrank the worker self-report.  A note is
   evidence to reconcile, never authority.  The observed change set is never
   normalised, widened, or repaired from a declaration.
2. Path authority is fail-closed.  A forbidden path stays forbidden even when
   the worker declared it, even when every test passed, and even when a path
   expansion receipt names it.
3. Validation is only meaningful for the state it validated.  A receipt bound
   to an earlier state cannot certify a later final state, and worker prose can
   never mint a validation receipt.

The reconciliation core is pure and import-time inert.  It performs no
repository traversal, no source read, no validation execution, no command
execution, no patch generation or application, no model call, no network call,
and no write.  Fact collection lives behind the separately bounded
``core.post_run_observation`` adapter; tests construct facts directly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from core.repository_path_policy import (
    MAX_CANONICAL_RELATIVE_PATH_LENGTH,
    is_safe_repository_relative_path,
)


PHASE_ID = "CHECK.1"

AUTHORIZED_PATH_SCHEMA_VERSION = "check_1_authorized_path_v1"
AUTHORIZATION_SCHEMA_VERSION = "check_1_execution_authorization_v1"
WORKER_REPORT_SCHEMA_VERSION = "check_1_worker_report_v1"
OBSERVED_FACTS_SCHEMA_VERSION = "check_1_observed_post_run_facts_v1"
REQUEST_SCHEMA_VERSION = "check_1_reconciliation_request_v1"
RESULT_SCHEMA_VERSION = "check_1_post_run_reconciliation_v1"


# ── Bounded vocabularies ──────────────────────────────────────────────────────

#: What objectively happened to one repository path.  ``renamed`` exists only
#: because an upstream collector may authoritatively support it; CHECK.1 never
#: infers a rename from a delete plus an add.
CHANGE_ADDED = "added"
CHANGE_DELETED = "deleted"
CHANGE_MODIFIED = "modified"
CHANGE_RENAMED = "renamed"

CHANGE_KINDS: tuple[str, ...] = (
    CHANGE_ADDED,
    CHANGE_DELETED,
    CHANGE_MODIFIED,
    CHANGE_RENAMED,
)

#: Path authority granted by the upstream execution authorization.  Read
#: authority is never write authority, and execute authority is never write
#: authority.
PATH_AUTHORITY_WRITABLE = "writable"
PATH_AUTHORITY_WRITABLE_WITH_REVIEW = "writable_with_review"
PATH_AUTHORITY_SUPPORTING_READ_ONLY = "supporting_read_only"
PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY = "validation_execute_only"
PATH_AUTHORITY_FORBIDDEN = "forbidden"
#: Not a grantable authority — the state of a path the authorization never
#: mentioned at all.
PATH_AUTHORITY_UNAUTHORIZED = "unauthorized"

AUTHORIZED_PATH_AUTHORITIES: tuple[str, ...] = (
    PATH_AUTHORITY_WRITABLE,
    PATH_AUTHORITY_WRITABLE_WITH_REVIEW,
    PATH_AUTHORITY_SUPPORTING_READ_ONLY,
    PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY,
    PATH_AUTHORITY_FORBIDDEN,
)

PATH_AUTHORITIES: tuple[str, ...] = (
    *AUTHORIZED_PATH_AUTHORITIES,
    PATH_AUTHORITY_UNAUTHORIZED,
)

#: The only two authorities under which a write is inside the contract.
WRITE_BEARING_AUTHORITIES: frozenset[str] = frozenset(
    {PATH_AUTHORITY_WRITABLE, PATH_AUTHORITY_WRITABLE_WITH_REVIEW}
)

#: Why a path is forbidden.  The first five values are exactly the categories
#: ``core.patch_safety`` already emits; the remainder preserve the non-writable
#: states established by the existing file-capability and freshness contracts.
#: CHECK.1 never rediscovers any of them semantically.
FORBIDDEN_TRAVERSAL = "traversal"
FORBIDDEN_PROTECTED_DIR = "protected_dir"
FORBIDDEN_ENV = "env"
FORBIDDEN_TEST = "test"
FORBIDDEN_BENCHMARK_VALIDATION = "benchmark_validation"
FORBIDDEN_GENERATED = "generated"
FORBIDDEN_TEMPORARY = "temporary"
FORBIDDEN_SENSITIVE = "sensitive"
FORBIDDEN_SYMLINKED = "symlinked"
FORBIDDEN_STALE = "stale"
FORBIDDEN_REPLACED = "replaced"
FORBIDDEN_OUTSIDE_SCOPE = "outside_scope"
FORBIDDEN_OTHER = "other"

FORBIDDEN_REASONS: tuple[str, ...] = (
    FORBIDDEN_TRAVERSAL,
    FORBIDDEN_PROTECTED_DIR,
    FORBIDDEN_ENV,
    FORBIDDEN_TEST,
    FORBIDDEN_BENCHMARK_VALIDATION,
    FORBIDDEN_GENERATED,
    FORBIDDEN_TEMPORARY,
    FORBIDDEN_SENSITIVE,
    FORBIDDEN_SYMLINKED,
    FORBIDDEN_STALE,
    FORBIDDEN_REPLACED,
    FORBIDDEN_OUTSIDE_SCOPE,
    FORBIDDEN_OTHER,
)

#: How one declared or observed change reconciles.
CLASSIFICATION_MATCHED = "matched"
CLASSIFICATION_UNDECLARED = "undeclared_change"
CLASSIFICATION_DECLARED_UNOBSERVED = "declared_but_unobserved_change"
CLASSIFICATION_KIND_MISMATCH = "declared_change_kind_mismatch"
CLASSIFICATION_IDENTITY_MISMATCH = "declared_change_identity_mismatch"

CHANGE_CLASSIFICATIONS: tuple[str, ...] = (
    CLASSIFICATION_MATCHED,
    CLASSIFICATION_UNDECLARED,
    CLASSIFICATION_DECLARED_UNOBSERVED,
    CLASSIFICATION_KIND_MISMATCH,
    CLASSIFICATION_IDENTITY_MISMATCH,
)

#: Consequence of one finding.  Deliberately three explicit bands, never a
#: numeric risk score.
SEVERITY_INFORMATIONAL = "informational"
SEVERITY_SUSPICIOUS = "suspicious"
SEVERITY_BLOCKED = "blocked"

SEVERITIES: tuple[str, ...] = (
    SEVERITY_INFORMATIONAL,
    SEVERITY_SUSPICIOUS,
    SEVERITY_BLOCKED,
)

#: What the worker said about its own run.
WORKER_CLAIM_SUCCESS = "success"
WORKER_CLAIM_PARTIAL = "partial"
WORKER_CLAIM_FAILED = "failed"
WORKER_CLAIM_BLOCKED = "blocked"

WORKER_STATUS_CLAIMS: tuple[str, ...] = (
    WORKER_CLAIM_SUCCESS,
    WORKER_CLAIM_PARTIAL,
    WORKER_CLAIM_FAILED,
    WORKER_CLAIM_BLOCKED,
)

#: A bounded class of validation, never a command string.  CHECK.1 stores no
#: command text and could not run one if it did.
VALIDATION_UNIT_TESTS = "unit_tests"
VALIDATION_TARGETED_REGRESSION = "targeted_regression"
VALIDATION_STATIC_CHECK = "static_check"
VALIDATION_BUILD = "build"
VALIDATION_BENCHMARK = "benchmark"
VALIDATION_INVARIANT_CHECK = "invariant_check"

VALIDATION_KINDS: tuple[str, ...] = (
    VALIDATION_UNIT_TESTS,
    VALIDATION_TARGETED_REGRESSION,
    VALIDATION_STATIC_CHECK,
    VALIDATION_BUILD,
    VALIDATION_BENCHMARK,
    VALIDATION_INVARIANT_CHECK,
)

#: What a validation receipt reports.
RECEIPT_PASSED = "passed"
RECEIPT_FAILED = "failed"
RECEIPT_ERRORED = "errored"
RECEIPT_TIMED_OUT = "timed_out"
RECEIPT_SKIPPED = "skipped"

RECEIPT_RESULTS: tuple[str, ...] = (
    RECEIPT_PASSED,
    RECEIPT_FAILED,
    RECEIPT_ERRORED,
    RECEIPT_TIMED_OUT,
    RECEIPT_SKIPPED,
)

#: Receipt results that are an outright validation failure.
_FAILING_RECEIPT_RESULTS: frozenset[str] = frozenset(
    {RECEIPT_FAILED, RECEIPT_ERRORED, RECEIPT_TIMED_OUT}
)

#: What the worker claims about a validation it says it performed.
DECLARED_VALIDATION_PASSED = "passed"
DECLARED_VALIDATION_FAILED = "failed"
DECLARED_VALIDATION_NOT_RUN = "not_run"

DECLARED_VALIDATION_RESULTS: tuple[str, ...] = (
    DECLARED_VALIDATION_PASSED,
    DECLARED_VALIDATION_FAILED,
    DECLARED_VALIDATION_NOT_RUN,
)

#: Coverage state of one validation expectation, or of one receipt that no
#: expectation asked for.
COVERAGE_SATISFIED = "satisfied"
COVERAGE_MISSING = "missing"
COVERAGE_FAILED = "failed"
COVERAGE_STALE = "stale"
COVERAGE_SCOPE_MISMATCH = "scope_mismatch"
COVERAGE_RECEIPT_INVALID = "receipt_invalid"
COVERAGE_OPTIONAL_MISSING = "optional_missing"
COVERAGE_ADDITIONAL_OBSERVED = "additional_observed"

VALIDATION_COVERAGE_STATES: tuple[str, ...] = (
    COVERAGE_SATISFIED,
    COVERAGE_MISSING,
    COVERAGE_FAILED,
    COVERAGE_STALE,
    COVERAGE_SCOPE_MISMATCH,
    COVERAGE_RECEIPT_INVALID,
    COVERAGE_OPTIONAL_MISSING,
    COVERAGE_ADDITIONAL_OBSERVED,
)

#: Coverage states under which a *required* expectation is not discharged.
_UNDISCHARGED_COVERAGE: frozenset[str] = frozenset(
    {
        COVERAGE_MISSING,
        COVERAGE_FAILED,
        COVERAGE_STALE,
        COVERAGE_SCOPE_MISMATCH,
        COVERAGE_RECEIPT_INVALID,
    }
)

#: A preservation obligation the upstream task contract carried.  CHECK.1
#: preserves its presence; it cannot decide semantically whether behaviour was
#: preserved.
OBLIGATION_BEHAVIOR_PRESERVATION = "behavior_preservation"
OBLIGATION_INTERFACE_PRESERVATION = "interface_preservation"
OBLIGATION_PERFORMANCE_PRESERVATION = "performance_preservation"
OBLIGATION_COMPATIBILITY_PRESERVATION = "compatibility_preservation"
OBLIGATION_SCOPE_PRESERVATION = "scope_preservation"

PRESERVATION_OBLIGATION_KINDS: tuple[str, ...] = (
    OBLIGATION_BEHAVIOR_PRESERVATION,
    OBLIGATION_INTERFACE_PRESERVATION,
    OBLIGATION_PERFORMANCE_PRESERVATION,
    OBLIGATION_COMPATIBILITY_PRESERVATION,
    OBLIGATION_SCOPE_PRESERVATION,
)

OBLIGATION_UNRESOLVED = "unresolved_semantic_check_required"
OBLIGATION_CERTIFIED = "certified_by_validation_receipt"
OBLIGATION_CERTIFICATION_UNSATISFIED = "certifying_validation_not_satisfied"

PRESERVATION_OBLIGATION_STATES: tuple[str, ...] = (
    OBLIGATION_UNRESOLVED,
    OBLIGATION_CERTIFIED,
    OBLIGATION_CERTIFICATION_UNSATISFIED,
)

#: The whole post-run status vocabulary.  It names contract agreement only.
#: There is deliberately no ``semantically_correct`` / ``goal_satisfied`` value.
STATUS_RECONCILED = "reconciled"
STATUS_RECONCILED_WITH_WARNINGS = "reconciled_with_warnings"
STATUS_INCOMPLETE = "incomplete"
STATUS_SUSPICIOUS = "suspicious"
STATUS_BLOCKED = "blocked"
STATUS_INCONSISTENT_INPUT = "inconsistent_input"

RECONCILIATION_STATUSES: tuple[str, ...] = (
    STATUS_RECONCILED,
    STATUS_RECONCILED_WITH_WARNINGS,
    STATUS_INCOMPLETE,
    STATUS_SUSPICIOUS,
    STATUS_BLOCKED,
    STATUS_INCONSISTENT_INPUT,
)


# ── Reason codes ──────────────────────────────────────────────────────────────

# Reasons name structural work CHECK.1 actually performed, never a conclusion
# about the implementation.
CHECK_AUTHORIZATION_BOUND = "CHECK_AUTHORIZATION_BOUND"
CHECK_WORKER_REPORT_BOUND = "CHECK_WORKER_REPORT_BOUND"
CHECK_OBSERVED_FACTS_BOUND = "CHECK_OBSERVED_FACTS_BOUND"
CHECK_DECLARED_VS_OBSERVED_COMPARED = "CHECK_DECLARED_VS_OBSERVED_COMPARED"
CHECK_CHANGE_SCOPE_CHECKED = "CHECK_CHANGE_SCOPE_CHECKED"
CHECK_FORBIDDEN_PATHS_CHECKED = "CHECK_FORBIDDEN_PATHS_CHECKED"
CHECK_VALIDATION_EXPECTATIONS_COMPARED = "CHECK_VALIDATION_EXPECTATIONS_COMPARED"
CHECK_VALIDATION_RECEIPTS_CHECKED = "CHECK_VALIDATION_RECEIPTS_CHECKED"
CHECK_VALIDATION_FRESHNESS_CHECKED = "CHECK_VALIDATION_FRESHNESS_CHECKED"
CHECK_WORKER_STATUS_CLAIM_COMPARED = "CHECK_WORKER_STATUS_CLAIM_COMPARED"
CHECK_FINAL_STATE_BINDING_CHECKED = "CHECK_FINAL_STATE_BINDING_CHECKED"
CHECK_PRESERVATION_OBLIGATIONS_CARRIED = "CHECK_PRESERVATION_OBLIGATIONS_CARRIED"
CHECK_NO_SEMANTIC_REVIEW_PERFORMED = "CHECK_NO_SEMANTIC_REVIEW_PERFORMED"

RECONCILIATION_REASONS: tuple[str, ...] = (
    CHECK_AUTHORIZATION_BOUND,
    CHECK_WORKER_REPORT_BOUND,
    CHECK_OBSERVED_FACTS_BOUND,
    CHECK_DECLARED_VS_OBSERVED_COMPARED,
    CHECK_CHANGE_SCOPE_CHECKED,
    CHECK_FORBIDDEN_PATHS_CHECKED,
    CHECK_VALIDATION_EXPECTATIONS_COMPARED,
    CHECK_VALIDATION_RECEIPTS_CHECKED,
    CHECK_VALIDATION_FRESHNESS_CHECKED,
    CHECK_WORKER_STATUS_CLAIM_COMPARED,
    CHECK_FINAL_STATE_BINDING_CHECKED,
    CHECK_PRESERVATION_OBLIGATIONS_CARRIED,
    CHECK_NO_SEMANTIC_REVIEW_PERFORMED,
)


# Fatal input inconsistencies: the supplied fact set cannot be reconciled at
# all.  These are separate from substantive findings about the run.
INCONSISTENT_TASK_CONTRACT_FINGERPRINT = "task_contract_fingerprint_mismatch"
INCONSISTENT_AUTHORIZATION_FINGERPRINT = (
    "execution_authorization_fingerprint_mismatch"
)
INCONSISTENT_WORKER_REPORT_FINGERPRINT = "worker_report_fingerprint_mismatch"
INCONSISTENT_OBSERVED_FACTS_FINGERPRINT = "observed_facts_fingerprint_mismatch"
INCONSISTENT_VALIDATION_RECEIPT_FINGERPRINT = (
    "validation_receipt_fingerprint_mismatch"
)
INCONSISTENT_RUN_IDENTITY = "execution_run_identity_mismatch"
INCONSISTENT_REPOSITORY_IDENTITY = "repository_identity_mismatch"
INCONSISTENT_STATE_CHAIN = "execution_state_chain_broken"
INCONSISTENT_RENAME_UNSUPPORTED = "rename_relation_unsupported_by_facts"
INCONSISTENT_EXPANSION_OVER_FORBIDDEN = "path_expansion_over_forbidden_path"
INCONSISTENT_UPSTREAM_AUTHORITY = "upstream_authority_asserted"
INCONSISTENT_UPSTREAM_GUARDRAIL = "upstream_guardrail_violated"

# Substantive inconsistencies between the contract, the report and the facts.
INCONSISTENT_FORBIDDEN_CHANGE = "forbidden_path_changed"
INCONSISTENT_OUT_OF_SCOPE_CHANGE = "out_of_authorized_scope_change"
INCONSISTENT_SUPPORTING_FILE_WRITTEN = "supporting_read_only_file_written"
INCONSISTENT_VALIDATION_FILE_WRITTEN = "validation_only_file_written"
INCONSISTENT_WORKER_SCOPE = "out_of_worker_scope_change"
INCONSISTENT_UNDECLARED_CHANGE = "undeclared_change_observed"
INCONSISTENT_DECLARED_UNOBSERVED = "declared_change_not_observed"
INCONSISTENT_DECLARED_KIND = "declared_change_kind_differs"
INCONSISTENT_DECLARED_IDENTITY = "declared_change_identity_differs"
INCONSISTENT_NO_CHANGE_CLAIM = "no_change_claimed_while_changes_observed"
INCONSISTENT_CHANGE_CLAIM_WITHOUT_CHANGES = (
    "changes_claimed_while_none_observed"
)
INCONSISTENT_VALIDATION_MISSING = "required_validation_missing"
INCONSISTENT_VALIDATION_FAILED = "required_validation_failed"
INCONSISTENT_VALIDATION_STALE = "validation_stale_for_final_state"
INCONSISTENT_VALIDATION_SCOPE = "validation_scope_mismatch"
INCONSISTENT_VALIDATION_RECEIPT_INVALID = "validation_receipt_invalid"
INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM = "unverified_worker_validation_claim"
INCONSISTENT_POST_VALIDATION_MUTATION = "state_mutated_after_validation"
INCONSISTENT_WORKER_SUCCESS_CLAIM = "worker_success_claim_inconsistent"
INCONSISTENT_WORKER_STATUS_CLAIM = "worker_status_claim_inconsistent"

RECONCILIATION_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_TASK_CONTRACT_FINGERPRINT,
    INCONSISTENT_AUTHORIZATION_FINGERPRINT,
    INCONSISTENT_WORKER_REPORT_FINGERPRINT,
    INCONSISTENT_OBSERVED_FACTS_FINGERPRINT,
    INCONSISTENT_VALIDATION_RECEIPT_FINGERPRINT,
    INCONSISTENT_RUN_IDENTITY,
    INCONSISTENT_REPOSITORY_IDENTITY,
    INCONSISTENT_STATE_CHAIN,
    INCONSISTENT_RENAME_UNSUPPORTED,
    INCONSISTENT_EXPANSION_OVER_FORBIDDEN,
    INCONSISTENT_UPSTREAM_AUTHORITY,
    INCONSISTENT_UPSTREAM_GUARDRAIL,
    INCONSISTENT_FORBIDDEN_CHANGE,
    INCONSISTENT_OUT_OF_SCOPE_CHANGE,
    INCONSISTENT_SUPPORTING_FILE_WRITTEN,
    INCONSISTENT_VALIDATION_FILE_WRITTEN,
    INCONSISTENT_WORKER_SCOPE,
    INCONSISTENT_UNDECLARED_CHANGE,
    INCONSISTENT_DECLARED_UNOBSERVED,
    INCONSISTENT_DECLARED_KIND,
    INCONSISTENT_DECLARED_IDENTITY,
    INCONSISTENT_NO_CHANGE_CLAIM,
    INCONSISTENT_CHANGE_CLAIM_WITHOUT_CHANGES,
    INCONSISTENT_VALIDATION_MISSING,
    INCONSISTENT_VALIDATION_FAILED,
    INCONSISTENT_VALIDATION_STALE,
    INCONSISTENT_VALIDATION_SCOPE,
    INCONSISTENT_VALIDATION_RECEIPT_INVALID,
    INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM,
    INCONSISTENT_POST_VALIDATION_MUTATION,
    INCONSISTENT_WORKER_SUCCESS_CLAIM,
    INCONSISTENT_WORKER_STATUS_CLAIM,
)

#: Inconsistencies that make the supplied fact set unusable.  Their presence
#: short-circuits reconciliation to ``inconsistent_input``.
_INPUT_INCONSISTENCIES: frozenset[str] = frozenset(
    {
        INCONSISTENT_TASK_CONTRACT_FINGERPRINT,
        INCONSISTENT_AUTHORIZATION_FINGERPRINT,
        INCONSISTENT_WORKER_REPORT_FINGERPRINT,
        INCONSISTENT_OBSERVED_FACTS_FINGERPRINT,
        INCONSISTENT_VALIDATION_RECEIPT_FINGERPRINT,
        INCONSISTENT_RUN_IDENTITY,
        INCONSISTENT_REPOSITORY_IDENTITY,
        INCONSISTENT_STATE_CHAIN,
        INCONSISTENT_RENAME_UNSUPPORTED,
        INCONSISTENT_EXPANSION_OVER_FORBIDDEN,
        INCONSISTENT_UPSTREAM_AUTHORITY,
        INCONSISTENT_UPSTREAM_GUARDRAIL,
    }
)

#: Inconsistencies that block certification outright.
_BLOCKING_INCONSISTENCIES: frozenset[str] = frozenset(
    {
        INCONSISTENT_FORBIDDEN_CHANGE,
        INCONSISTENT_OUT_OF_SCOPE_CHANGE,
        INCONSISTENT_SUPPORTING_FILE_WRITTEN,
        INCONSISTENT_VALIDATION_FILE_WRITTEN,
        INCONSISTENT_WORKER_SCOPE,
        INCONSISTENT_VALIDATION_FAILED,
    }
)


# Per-finding reason codes.  Bounded and explicit; never free prose.
FINDING_DECLARED = "declared_by_worker"
FINDING_UNDECLARED = "not_declared_by_worker"
FINDING_NOT_OBSERVED = "not_present_in_observed_changes"
FINDING_WRITE_AUTHORIZED = "write_authorized_for_path"
FINDING_WRITE_NOT_AUTHORIZED = "write_not_authorized_for_path"
FINDING_REVIEW_REQUIRED = "path_write_requires_review"
FINDING_FORBIDDEN_PATH = "path_is_forbidden"
FINDING_OUTSIDE_AUTHORIZED_SCOPE = "path_outside_authorized_scope"
FINDING_SUPPORTING_READ_ONLY = "path_is_supporting_read_only"
FINDING_VALIDATION_EXECUTE_ONLY = "path_is_validation_execute_only"
FINDING_KIND_MISMATCH = "declared_change_kind_differs"
FINDING_IDENTITY_MISMATCH = "declared_change_identity_differs"
FINDING_WORKER_SCOPE = "path_owned_by_another_worker"
FINDING_PATH_EXPANSION_APPLIED = "authorized_by_path_expansion_receipt"

CHANGE_FINDING_REASONS: tuple[str, ...] = (
    FINDING_DECLARED,
    FINDING_UNDECLARED,
    FINDING_NOT_OBSERVED,
    FINDING_WRITE_AUTHORIZED,
    FINDING_WRITE_NOT_AUTHORIZED,
    FINDING_REVIEW_REQUIRED,
    FINDING_FORBIDDEN_PATH,
    FINDING_OUTSIDE_AUTHORIZED_SCOPE,
    FINDING_SUPPORTING_READ_ONLY,
    FINDING_VALIDATION_EXECUTE_ONLY,
    FINDING_KIND_MISMATCH,
    FINDING_IDENTITY_MISMATCH,
    FINDING_WORKER_SCOPE,
    FINDING_PATH_EXPANSION_APPLIED,
)

VALIDATION_REASON_CURRENT = "receipt_binds_final_state"
VALIDATION_REASON_NO_RECEIPT = "no_matching_receipt"
VALIDATION_REASON_SCOPE_MISMATCH = "receipt_scope_differs"
VALIDATION_REASON_RECEIPT_INVALID = "receipt_binding_invalid"
VALIDATION_REASON_RESULT_FAILED = "receipt_reports_failure"
VALIDATION_REASON_SKIPPED = "receipt_reports_skipped"
VALIDATION_REASON_STALE = "receipt_state_is_not_final_state"
VALIDATION_REASON_OPTIONAL = "expectation_is_optional"
VALIDATION_REASON_UNVERIFIED_CLAIM = "worker_claimed_without_receipt"
VALIDATION_REASON_ADDITIONAL = "receipt_has_no_upstream_expectation"

VALIDATION_FINDING_REASONS: tuple[str, ...] = (
    VALIDATION_REASON_CURRENT,
    VALIDATION_REASON_NO_RECEIPT,
    VALIDATION_REASON_SCOPE_MISMATCH,
    VALIDATION_REASON_RECEIPT_INVALID,
    VALIDATION_REASON_RESULT_FAILED,
    VALIDATION_REASON_SKIPPED,
    VALIDATION_REASON_STALE,
    VALIDATION_REASON_OPTIONAL,
    VALIDATION_REASON_UNVERIFIED_CLAIM,
    VALIDATION_REASON_ADDITIONAL,
)


# What still has to happen after CHECK.1.  ``semantic_goal_review_required``
# and ``human_review_required`` are present on *every* result, including a
# fully reconciled one.
UNRESOLVED_SEMANTIC_GOAL_REVIEW = "semantic_goal_review_required"
UNRESOLVED_SEMANTIC_PRESERVATION = "semantic_preservation_unresolved"
UNRESOLVED_VALIDATION_COVERAGE = "validation_coverage_required"
UNRESOLVED_VALIDATION_FRESHNESS = "current_state_validation_required"
UNRESOLVED_WORKER_REPORT_CORRECTION = "worker_report_correction_required"
UNRESOLVED_SCOPE_AUTHORIZATION = "scope_authorization_required"
UNRESOLVED_WORKER_SCOPE_OWNERSHIP = "worker_scope_ownership_unavailable"
UNRESOLVED_FINAL_STATE_BINDING = "final_state_binding_required"
UNRESOLVED_UPSTREAM_INPUT = "upstream_input_correction_required"
UNRESOLVED_HUMAN_REVIEW = "human_review_required"

RECONCILIATION_UNRESOLVED_REQUIREMENTS: tuple[str, ...] = (
    UNRESOLVED_SEMANTIC_GOAL_REVIEW,
    UNRESOLVED_SEMANTIC_PRESERVATION,
    UNRESOLVED_VALIDATION_COVERAGE,
    UNRESOLVED_VALIDATION_FRESHNESS,
    UNRESOLVED_WORKER_REPORT_CORRECTION,
    UNRESOLVED_SCOPE_AUTHORIZATION,
    UNRESOLVED_WORKER_SCOPE_OWNERSHIP,
    UNRESOLVED_FINAL_STATE_BINDING,
    UNRESOLVED_UPSTREAM_INPUT,
    UNRESOLVED_HUMAN_REVIEW,
)


#: What ``reconciled`` means, stated in the contract itself so no consumer can
#: read it as a semantic verdict.
RECONCILED_MEANING = (
    "The observed execution facts agree with the bounded execution contract, "
    "the worker self-report, path authority and required validation receipts. "
    "It does not mean the implementation satisfies the user's semantic goal; "
    "that review is CHECK.2 and remains outstanding."
)


# ── Finite bounds ─────────────────────────────────────────────────────────────

MAX_IDENTIFIER_CHARS = 160
MAX_PATH_CHARS = MAX_CANONICAL_RELATIVE_PATH_LENGTH
MAX_TEXT_CHARS = 480
MAX_AUTHORIZED_PATHS = 256
MAX_PATH_EXPANSION_RECEIPTS = 32
MAX_VALIDATION_EXPECTATIONS = 32
MAX_VALIDATION_RECEIPTS = 64
MAX_TARGET_SCOPE_ENTRIES = 32
MAX_DECLARED_CHANGES = 256
MAX_OBSERVED_CHANGES = 256
MAX_DECLARED_VALIDATION_ACTIONS = 32
MAX_PRESERVATION_OBLIGATIONS = 32
MAX_LIMITATIONS = 32
MAX_UNRESOLVED_ITEMS = 32
MAX_CHANGE_FINDINGS = 512
MAX_VALIDATION_FINDINGS = 128
MAX_PRESERVATION_FINDINGS = 32
MAX_SUMMARY_PATHS = 256


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_sha256(value: object, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not _is_sha256(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _bounded_text(value: object, label: str, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} contains a control character")


def _bounded_identifier(value: object, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    _bounded_text(value, label, MAX_IDENTIFIER_CHARS)


def _bounded_path(value: object, label: str, *, optional: bool = False) -> None:
    """Validate one canonical repository-relative path spelling.

    Path shape is delegated to the frozen repository path policy so CHECK.1
    cannot invent a second, drifting spelling rule.  The check is lexical: no
    filesystem is consulted.

    The one added guard is a leading separator.  ``Path("/etc/passwd")`` is not
    absolute on Windows, where only a drive root counts, so a POSIX-rooted
    spelling can pass a portable policy check.  ``core.patch_safety`` already
    rejects that exact shape at apply time; CHECK.1 fails closed the same way
    rather than reconciling a change to a path outside the repository.
    """

    if value is None and optional:
        return
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string path")
    if len(value) > MAX_PATH_CHARS:
        raise ValueError(f"{label} exceeds its finite bound")
    if value[:1] in {"/", "\\"}:
        raise ValueError(f"{label} must not start with a path separator")
    if not is_safe_repository_relative_path(value):
        raise ValueError(f"{label} is not a canonical repository-relative path")


def _bounded_tuple(values: object, maximum: int, label: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    if len(values) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")


def _validate_unique(values: tuple[str, ...], label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} values must be unique")


def _ordered_codes(codes: set[str], vocabulary: tuple[str, ...]) -> tuple[str, ...]:
    """Render a code set in canonical vocabulary order, deduplicated."""
    return tuple(value for value in vocabulary if value in codes)


def _ordered_vocabulary(
    values: tuple[str, ...], vocabulary: tuple[str, ...], label: str
) -> None:
    _bounded_tuple(values, len(vocabulary), label)
    _validate_unique(values, label)
    position = {value: ordinal for ordinal, value in enumerate(vocabulary)}
    if any(value not in position for value in values):
        raise ValueError(f"{label} contains an unsupported value")
    if tuple(sorted(values, key=position.__getitem__)) != values:
        raise ValueError(f"{label} must use canonical vocabulary order")


def _canonical_paths(values: object, label: str) -> tuple[str, ...]:
    """Canonicalise an unordered path set: validated, deduplicated, sorted."""
    _bounded_tuple(values, MAX_TARGET_SCOPE_ENTRIES, label)
    for value in values:
        _bounded_path(value, label)
    _validate_unique(values, label)
    return tuple(sorted(values))


# ── Supplied records ──────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class AuthorizedPath:
    """One path the execution authorization explicitly classified."""

    path: str
    authority: str
    forbidden_reason: str | None = None
    worker_id: str | None = None

    def __post_init__(self) -> None:
        _bounded_path(self.path, "authorized path")
        if self.authority not in AUTHORIZED_PATH_AUTHORITIES:
            raise ValueError(f"unsupported path authority: {self.authority!r}")
        if self.authority == PATH_AUTHORITY_FORBIDDEN:
            if self.forbidden_reason not in FORBIDDEN_REASONS:
                raise ValueError("a forbidden path must state a bounded reason")
        elif self.forbidden_reason is not None:
            raise ValueError("only a forbidden path may carry a forbidden reason")
        _bounded_identifier(self.worker_id, "authorized path worker id", optional=True)

    @property
    def write_authorized(self) -> bool:
        return self.authority in WRITE_BEARING_AUTHORITIES

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "authority": self.authority,
            "forbidden_reason": self.forbidden_reason,
            "worker_id": self.worker_id,
        }


@dataclass(frozen=True, slots=True)
class PathExpansionReceipt:
    """A bounded, explicitly approved widening of the authorized path set.

    An expansion receipt is the *only* route by which a path outside the
    original authorization may be treated as authorized.  It can never reach a
    path the authorization marked forbidden.
    """

    path: str
    authority: str
    approval_receipt_sha256: str

    def __post_init__(self) -> None:
        _bounded_path(self.path, "path expansion path")
        if self.authority not in WRITE_BEARING_AUTHORITIES:
            raise ValueError(
                "a path expansion receipt may only grant a write-bearing authority"
            )
        _require_sha256(
            self.approval_receipt_sha256, "path expansion approval receipt"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "authority": self.authority,
            "approval_receipt_sha256": self.approval_receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class ValidationExpectation:
    """One validation the upstream contract requires or offers."""

    validation_id: str
    validation_kind: str
    required: bool
    target_scope: tuple[str, ...] = ()
    expected_state_fingerprint: str | None = None

    def __post_init__(self) -> None:
        _bounded_identifier(self.validation_id, "validation id")
        if self.validation_kind not in VALIDATION_KINDS:
            raise ValueError(f"unsupported validation kind: {self.validation_kind!r}")
        if not isinstance(self.required, bool):
            raise TypeError("validation expectation required must be a bool")
        _canonical_paths(self.target_scope, "validation expectation target scope")
        if tuple(sorted(self.target_scope)) != self.target_scope:
            raise ValueError("validation target scope must be canonically sorted")
        _require_sha256(
            self.expected_state_fingerprint,
            "validation expectation state fingerprint",
            optional=True,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "validation_kind": self.validation_kind,
            "required": self.required,
            "target_scope": list(self.target_scope),
            "expected_state_fingerprint": self.expected_state_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class PreservationObligation:
    """A commitment the task contract carried into execution.

    CHECK.1 preserves the obligation's presence and identity.  It decides
    nothing about whether behaviour was actually preserved.
    """

    obligation_id: str
    kind: str
    text_sha256: str
    certifying_validation_id: str | None = None

    def __post_init__(self) -> None:
        _bounded_identifier(self.obligation_id, "preservation obligation id")
        if self.kind not in PRESERVATION_OBLIGATION_KINDS:
            raise ValueError(f"unsupported preservation obligation kind: {self.kind!r}")
        _require_sha256(self.text_sha256, "preservation obligation text digest")
        _bounded_identifier(
            self.certifying_validation_id,
            "certifying validation id",
            optional=True,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "kind": self.kind,
            "text_sha256": self.text_sha256,
            "certifying_validation_id": self.certifying_validation_id,
        }


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    """What the execution was allowed to do, before it ran."""

    authorization_id: str
    execution_run_id: str
    repository_id: str
    task_contract_fingerprint: str
    pre_execution_state_fingerprint: str
    authorized_paths: tuple[AuthorizedPath, ...] = ()
    validation_expectations: tuple[ValidationExpectation, ...] = ()
    preservation_obligations: tuple[PreservationObligation, ...] = ()
    path_expansion_receipts: tuple[PathExpansionReceipt, ...] = ()
    worker_id: str | None = None
    schema_version: str = AUTHORIZATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(self.authorization_id, "authorization id")
        _bounded_identifier(self.execution_run_id, "execution run id")
        _bounded_identifier(self.repository_id, "repository id")
        _require_sha256(self.task_contract_fingerprint, "task contract fingerprint")
        _require_sha256(
            self.pre_execution_state_fingerprint, "pre-execution state fingerprint"
        )
        _bounded_tuple(
            self.authorized_paths, MAX_AUTHORIZED_PATHS, "authorized paths"
        )
        _bounded_tuple(
            self.validation_expectations,
            MAX_VALIDATION_EXPECTATIONS,
            "validation expectations",
        )
        _bounded_tuple(
            self.preservation_obligations,
            MAX_PRESERVATION_OBLIGATIONS,
            "preservation obligations",
        )
        _bounded_tuple(
            self.path_expansion_receipts,
            MAX_PATH_EXPANSION_RECEIPTS,
            "path expansion receipts",
        )
        if not all(type(item) is AuthorizedPath for item in self.authorized_paths):
            raise TypeError("authorized_paths must contain AuthorizedPath records")
        if not all(
            type(item) is ValidationExpectation
            for item in self.validation_expectations
        ):
            raise TypeError(
                "validation_expectations must contain ValidationExpectation records"
            )
        if not all(
            type(item) is PreservationObligation
            for item in self.preservation_obligations
        ):
            raise TypeError(
                "preservation_obligations must contain PreservationObligation records"
            )
        if not all(
            type(item) is PathExpansionReceipt
            for item in self.path_expansion_receipts
        ):
            raise TypeError(
                "path_expansion_receipts must contain PathExpansionReceipt records"
            )
        _validate_unique(
            tuple(item.path for item in self.authorized_paths), "authorized path"
        )
        _validate_unique(
            tuple(item.validation_id for item in self.validation_expectations),
            "validation expectation id",
        )
        _validate_unique(
            tuple(item.obligation_id for item in self.preservation_obligations),
            "preservation obligation id",
        )
        _validate_unique(
            tuple(item.path for item in self.path_expansion_receipts),
            "path expansion path",
        )
        _bounded_identifier(self.worker_id, "authorization worker id", optional=True)
        if self.schema_version != AUTHORIZATION_SCHEMA_VERSION:
            raise ValueError("unsupported execution authorization schema version")

    @property
    def declares_worker_ownership(self) -> bool:
        """Whether the upstream contract exposes per-worker path ownership."""
        return any(item.worker_id is not None for item in self.authorized_paths)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "authorization_id": self.authorization_id,
            "execution_run_id": self.execution_run_id,
            "repository_id": self.repository_id,
            "task_contract_fingerprint": self.task_contract_fingerprint,
            "pre_execution_state_fingerprint": self.pre_execution_state_fingerprint,
            "authorized_paths": [
                item.as_dict()
                for item in sorted(self.authorized_paths, key=lambda x: x.path)
            ],
            "validation_expectations": [
                item.as_dict()
                for item in sorted(
                    self.validation_expectations, key=lambda x: x.validation_id
                )
            ],
            "preservation_obligations": [
                item.as_dict()
                for item in sorted(
                    self.preservation_obligations, key=lambda x: x.obligation_id
                )
            ],
            "path_expansion_receipts": [
                item.as_dict()
                for item in sorted(self.path_expansion_receipts, key=lambda x: x.path)
            ],
            "worker_id": self.worker_id,
        }


def execution_authorization_fingerprint(
    authorization: ExecutionAuthorization,
) -> str:
    if type(authorization) is not ExecutionAuthorization:
        raise TypeError(
            "execution_authorization_fingerprint requires an exact "
            "ExecutionAuthorization"
        )
    return _fingerprint(authorization.as_dict())


@dataclass(frozen=True, slots=True)
class DeclaredChange:
    """One change the worker says it made.  Evidence, never authority."""

    path: str
    change_kind: str
    from_path: str | None = None
    expected_change_identity_sha256: str | None = None

    def __post_init__(self) -> None:
        _bounded_path(self.path, "declared change path")
        if self.change_kind not in CHANGE_KINDS:
            raise ValueError(f"unsupported declared change kind: {self.change_kind!r}")
        _bounded_path(self.from_path, "declared change from path", optional=True)
        if self.change_kind == CHANGE_RENAMED and self.from_path is None:
            raise ValueError("a declared rename must name its original path")
        if self.change_kind != CHANGE_RENAMED and self.from_path is not None:
            raise ValueError("only a declared rename may name an original path")
        if self.from_path is not None and self.from_path == self.path:
            raise ValueError("a declared rename must move between distinct paths")
        _require_sha256(
            self.expected_change_identity_sha256,
            "declared change identity",
            optional=True,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "change_kind": self.change_kind,
            "from_path": self.from_path,
            "expected_change_identity_sha256": self.expected_change_identity_sha256,
        }


@dataclass(frozen=True, slots=True)
class DeclaredValidationAction:
    """One validation the worker says it performed."""

    validation_kind: str
    declared_result: str
    validation_id: str | None = None

    def __post_init__(self) -> None:
        if self.validation_kind not in VALIDATION_KINDS:
            raise ValueError(
                f"unsupported declared validation kind: {self.validation_kind!r}"
            )
        if self.declared_result not in DECLARED_VALIDATION_RESULTS:
            raise ValueError(
                f"unsupported declared validation result: {self.declared_result!r}"
            )
        _bounded_identifier(
            self.validation_id, "declared validation id", optional=True
        )

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.validation_id or "", self.validation_kind, self.declared_result)

    def as_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "validation_kind": self.validation_kind,
            "declared_result": self.declared_result,
        }


@dataclass(frozen=True, slots=True)
class WorkerReport:
    """The worker's bounded, factual self-report.

    There is deliberately no free-form "everything looks good" field: a claim
    is a typed declaration that CHECK.1 reconciles against observed facts.
    """

    report_id: str
    execution_run_id: str
    declared_status: str
    declared_changes: tuple[DeclaredChange, ...] = ()
    declared_validation_actions: tuple[DeclaredValidationAction, ...] = ()
    declared_limitations: tuple[str, ...] = ()
    declared_unresolved_items: tuple[str, ...] = ()
    worker_id: str | None = None
    schema_version: str = WORKER_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(self.report_id, "worker report id")
        _bounded_identifier(self.execution_run_id, "worker report execution run id")
        if self.declared_status not in WORKER_STATUS_CLAIMS:
            raise ValueError(
                f"unsupported declared worker status: {self.declared_status!r}"
            )
        _bounded_tuple(
            self.declared_changes, MAX_DECLARED_CHANGES, "declared changes"
        )
        _bounded_tuple(
            self.declared_validation_actions,
            MAX_DECLARED_VALIDATION_ACTIONS,
            "declared validation actions",
        )
        _bounded_tuple(
            self.declared_limitations, MAX_LIMITATIONS, "declared limitations"
        )
        _bounded_tuple(
            self.declared_unresolved_items,
            MAX_UNRESOLVED_ITEMS,
            "declared unresolved items",
        )
        if not all(type(item) is DeclaredChange for item in self.declared_changes):
            raise TypeError("declared_changes must contain DeclaredChange records")
        if not all(
            type(item) is DeclaredValidationAction
            for item in self.declared_validation_actions
        ):
            raise TypeError(
                "declared_validation_actions must contain "
                "DeclaredValidationAction records"
            )
        _validate_unique(
            tuple(item.path for item in self.declared_changes), "declared change path"
        )
        if len(
            {item.key for item in self.declared_validation_actions}
        ) != len(self.declared_validation_actions):
            raise ValueError("declared validation actions must be unique")
        for text in (*self.declared_limitations, *self.declared_unresolved_items):
            _bounded_text(text, "worker report note", MAX_TEXT_CHARS)
        _bounded_identifier(self.worker_id, "worker report worker id", optional=True)
        if self.schema_version != WORKER_REPORT_SCHEMA_VERSION:
            raise ValueError("unsupported worker report schema version")

    def declared_changed_files(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                item.path
                for item in self.declared_changes
                if item.change_kind == CHANGE_MODIFIED
            )
        )

    def declared_created_files(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                item.path
                for item in self.declared_changes
                if item.change_kind == CHANGE_ADDED
            )
        )

    def declared_deleted_files(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                item.path
                for item in self.declared_changes
                if item.change_kind == CHANGE_DELETED
            )
        )

    def declared_renamed_files(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                item.path
                for item in self.declared_changes
                if item.change_kind == CHANGE_RENAMED
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "report_id": self.report_id,
            "execution_run_id": self.execution_run_id,
            "worker_id": self.worker_id,
            "declared_status": self.declared_status,
            "declared_changes": [
                item.as_dict()
                for item in sorted(self.declared_changes, key=lambda x: x.path)
            ],
            "declared_validation_actions": [
                item.as_dict()
                for item in sorted(
                    self.declared_validation_actions, key=lambda x: x.key
                )
            ],
            "declared_limitations": list(self.declared_limitations),
            "declared_unresolved_items": list(self.declared_unresolved_items),
        }


def worker_report_fingerprint(report: WorkerReport) -> str:
    if type(report) is not WorkerReport:
        raise TypeError("worker_report_fingerprint requires an exact WorkerReport")
    return _fingerprint(report.as_dict())


@dataclass(frozen=True, slots=True)
class ObservedChange:
    """One objectively observed repository change.

    Identity only: a path, a change kind and before/after content digests.  No
    diff text, patch body or source content is carried here or anywhere else in
    CHECK.1.
    """

    path: str
    change_kind: str
    before_sha256: str | None = None
    after_sha256: str | None = None
    from_path: str | None = None

    def __post_init__(self) -> None:
        _bounded_path(self.path, "observed change path")
        if self.change_kind not in CHANGE_KINDS:
            raise ValueError(f"unsupported observed change kind: {self.change_kind!r}")
        _require_sha256(self.before_sha256, "observed before digest", optional=True)
        _require_sha256(self.after_sha256, "observed after digest", optional=True)
        _bounded_path(self.from_path, "observed change from path", optional=True)
        if self.change_kind == CHANGE_ADDED and (
            self.before_sha256 is not None or self.after_sha256 is None
        ):
            raise ValueError("an added path has no before digest and one after digest")
        if self.change_kind == CHANGE_DELETED and (
            self.before_sha256 is None or self.after_sha256 is not None
        ):
            raise ValueError(
                "a deleted path has one before digest and no after digest"
            )
        if self.change_kind == CHANGE_MODIFIED and (
            self.before_sha256 is None or self.after_sha256 is None
        ):
            raise ValueError("a modified path carries both before and after digests")
        if self.change_kind == CHANGE_RENAMED and (
            self.from_path is None or self.after_sha256 is None
        ):
            raise ValueError(
                "a renamed path names its original path and its after digest"
            )
        if self.change_kind != CHANGE_RENAMED and self.from_path is not None:
            raise ValueError("only a renamed path may name an original path")
        if self.from_path is not None and self.from_path == self.path:
            raise ValueError("a rename must move between distinct paths")

    @property
    def change_identity_sha256(self) -> str:
        """Bind this change to one exact repository revision pair."""
        return _fingerprint(
            {
                "path": self.path,
                "change_kind": self.change_kind,
                "before_sha256": self.before_sha256,
                "after_sha256": self.after_sha256,
                "from_path": self.from_path,
            }
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "change_kind": self.change_kind,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "from_path": self.from_path,
            "change_identity_sha256": self.change_identity_sha256,
        }


@dataclass(frozen=True, slots=True)
class ValidationReceipt:
    """A receipt for one validation that actually executed elsewhere.

    CHECK.1 never produces a receipt and never runs the validation it
    describes; it only checks that a supplied receipt is bound to this run,
    this repository, this expectation and a known change state.
    """

    receipt_id: str
    validation_id: str
    execution_run_id: str
    repository_id: str
    validation_kind: str
    result: str
    state_fingerprint: str
    target_scope: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _bounded_identifier(self.receipt_id, "validation receipt id")
        _bounded_identifier(self.validation_id, "validation receipt validation id")
        _bounded_identifier(self.execution_run_id, "validation receipt run id")
        _bounded_identifier(self.repository_id, "validation receipt repository id")
        if self.validation_kind not in VALIDATION_KINDS:
            raise ValueError(
                f"unsupported validation receipt kind: {self.validation_kind!r}"
            )
        if self.result not in RECEIPT_RESULTS:
            raise ValueError(f"unsupported validation result: {self.result!r}")
        _require_sha256(self.state_fingerprint, "validation receipt state fingerprint")
        _canonical_paths(self.target_scope, "validation receipt target scope")
        if tuple(sorted(self.target_scope)) != self.target_scope:
            raise ValueError("validation receipt target scope must be sorted")

    def as_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "validation_id": self.validation_id,
            "execution_run_id": self.execution_run_id,
            "repository_id": self.repository_id,
            "validation_kind": self.validation_kind,
            "result": self.result,
            "state_fingerprint": self.state_fingerprint,
            "target_scope": list(self.target_scope),
        }


def validation_receipt_fingerprint(receipt: ValidationReceipt) -> str:
    if type(receipt) is not ValidationReceipt:
        raise TypeError(
            "validation_receipt_fingerprint requires an exact ValidationReceipt"
        )
    return _fingerprint(receipt.as_dict())


@dataclass(frozen=True, slots=True)
class ObservedPostRunFacts:
    """What objectively happened, as collected outside this pure core."""

    facts_id: str
    execution_run_id: str
    repository_id: str
    pre_execution_state_fingerprint: str
    post_execution_state_fingerprint: str
    final_state_fingerprint: str
    observed_changes: tuple[ObservedChange, ...] = ()
    validation_receipts: tuple[ValidationReceipt, ...] = ()
    post_validation_state_fingerprint: str | None = None
    rename_detection_supported: bool = False
    facts_collected_externally: bool = True
    schema_version: str = OBSERVED_FACTS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _bounded_identifier(self.facts_id, "observed facts id")
        _bounded_identifier(self.execution_run_id, "observed facts run id")
        _bounded_identifier(self.repository_id, "observed facts repository id")
        _require_sha256(
            self.pre_execution_state_fingerprint,
            "observed pre-execution state fingerprint",
        )
        _require_sha256(
            self.post_execution_state_fingerprint,
            "observed post-execution state fingerprint",
        )
        _require_sha256(self.final_state_fingerprint, "final state fingerprint")
        _require_sha256(
            self.post_validation_state_fingerprint,
            "post-validation state fingerprint",
            optional=True,
        )
        _bounded_tuple(
            self.observed_changes, MAX_OBSERVED_CHANGES, "observed changes"
        )
        _bounded_tuple(
            self.validation_receipts, MAX_VALIDATION_RECEIPTS, "validation receipts"
        )
        if not all(type(item) is ObservedChange for item in self.observed_changes):
            raise TypeError("observed_changes must contain ObservedChange records")
        if not all(
            type(item) is ValidationReceipt for item in self.validation_receipts
        ):
            raise TypeError(
                "validation_receipts must contain ValidationReceipt records"
            )
        _validate_unique(
            tuple(item.path for item in self.observed_changes), "observed change path"
        )
        _validate_unique(
            tuple(item.receipt_id for item in self.validation_receipts),
            "validation receipt id",
        )
        observed_paths = {item.path for item in self.observed_changes}
        for item in self.observed_changes:
            if item.from_path is not None and item.from_path in observed_paths:
                raise ValueError(
                    "a rename original path may not also be an observed change path"
                )
        if not isinstance(self.rename_detection_supported, bool):
            raise TypeError("rename_detection_supported must be a bool")
        if not isinstance(self.facts_collected_externally, bool):
            raise TypeError("facts_collected_externally must be a bool")
        if self.schema_version != OBSERVED_FACTS_SCHEMA_VERSION:
            raise ValueError("unsupported observed post-run facts schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "facts_id": self.facts_id,
            "execution_run_id": self.execution_run_id,
            "repository_id": self.repository_id,
            "pre_execution_state_fingerprint": self.pre_execution_state_fingerprint,
            "post_execution_state_fingerprint": self.post_execution_state_fingerprint,
            "post_validation_state_fingerprint": (
                self.post_validation_state_fingerprint
            ),
            "final_state_fingerprint": self.final_state_fingerprint,
            "observed_changes": [
                item.as_dict()
                for item in sorted(self.observed_changes, key=lambda x: x.path)
            ],
            "validation_receipts": [
                item.as_dict()
                for item in sorted(
                    self.validation_receipts, key=lambda x: x.receipt_id
                )
            ],
            "rename_detection_supported": self.rename_detection_supported,
            "facts_collected_externally": self.facts_collected_externally,
        }


def observed_post_run_facts_fingerprint(facts: ObservedPostRunFacts) -> str:
    if type(facts) is not ObservedPostRunFacts:
        raise TypeError(
            "observed_post_run_facts_fingerprint requires exact ObservedPostRunFacts"
        )
    return _fingerprint(facts.as_dict())


@dataclass(frozen=True, slots=True)
class PostRunReconciliationRequest:
    """One execution unit's supplied, immutable fact set.

    Exactly one authorization, one worker report and one observed fact set:
    CHECK.1 reconciles a single execution unit and never aggregates several
    workers into a combined verdict.
    """

    authorization: ExecutionAuthorization
    worker_report: WorkerReport
    observed_facts: ObservedPostRunFacts
    expected_task_contract_fingerprint: str
    expected_authorization_fingerprint: str
    expected_worker_report_fingerprint: str
    expected_observed_facts_fingerprint: str
    expected_validation_receipt_fingerprints: tuple[str, ...] = ()
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.authorization) is not ExecutionAuthorization:
            raise TypeError("authorization must be an ExecutionAuthorization")
        if type(self.worker_report) is not WorkerReport:
            raise TypeError("worker_report must be a WorkerReport")
        if type(self.observed_facts) is not ObservedPostRunFacts:
            raise TypeError("observed_facts must be ObservedPostRunFacts")
        _require_sha256(
            self.expected_task_contract_fingerprint,
            "expected task contract fingerprint",
        )
        _require_sha256(
            self.expected_authorization_fingerprint,
            "expected execution authorization fingerprint",
        )
        _require_sha256(
            self.expected_worker_report_fingerprint,
            "expected worker report fingerprint",
        )
        _require_sha256(
            self.expected_observed_facts_fingerprint,
            "expected observed facts fingerprint",
        )
        _bounded_tuple(
            self.expected_validation_receipt_fingerprints,
            MAX_VALIDATION_RECEIPTS,
            "expected validation receipt fingerprints",
        )
        for value in self.expected_validation_receipt_fingerprints:
            _require_sha256(value, "expected validation receipt fingerprint")
        _validate_unique(
            self.expected_validation_receipt_fingerprints,
            "expected validation receipt fingerprint",
        )
        if (
            tuple(sorted(self.expected_validation_receipt_fingerprints))
            != self.expected_validation_receipt_fingerprints
        ):
            raise ValueError(
                "expected validation receipt fingerprints must be canonically sorted"
            )
        if self.schema_version != REQUEST_SCHEMA_VERSION:
            raise ValueError("unsupported reconciliation request schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "authorization": self.authorization.as_dict(),
            "worker_report": self.worker_report.as_dict(),
            "observed_facts": self.observed_facts.as_dict(),
            "expected_task_contract_fingerprint": (
                self.expected_task_contract_fingerprint
            ),
            "expected_authorization_fingerprint": (
                self.expected_authorization_fingerprint
            ),
            "expected_worker_report_fingerprint": (
                self.expected_worker_report_fingerprint
            ),
            "expected_observed_facts_fingerprint": (
                self.expected_observed_facts_fingerprint
            ),
            "expected_validation_receipt_fingerprints": list(
                self.expected_validation_receipt_fingerprints
            ),
        }


def reconciliation_request_fingerprint(
    request: PostRunReconciliationRequest,
) -> str:
    if type(request) is not PostRunReconciliationRequest:
        raise TypeError(
            "reconciliation_request_fingerprint requires an exact "
            "PostRunReconciliationRequest"
        )
    return _fingerprint(request.as_dict())


# ── Derived records ───────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ChangeSummary:
    """A path-level summary.  Never a diff, never file content."""

    added_paths: tuple[str, ...] = ()
    deleted_paths: tuple[str, ...] = ()
    modified_paths: tuple[str, ...] = ()
    renamed_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label, values in (
            ("added", self.added_paths),
            ("deleted", self.deleted_paths),
            ("modified", self.modified_paths),
            ("renamed", self.renamed_paths),
        ):
            _bounded_tuple(values, MAX_SUMMARY_PATHS, f"{label} summary paths")
            _validate_unique(values, f"{label} summary path")
            if tuple(sorted(values)) != values:
                raise ValueError(f"{label} summary paths must be canonically sorted")

    @property
    def is_empty(self) -> bool:
        return not (
            self.added_paths
            or self.deleted_paths
            or self.modified_paths
            or self.renamed_paths
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "added_paths": list(self.added_paths),
            "deleted_paths": list(self.deleted_paths),
            "modified_paths": list(self.modified_paths),
            "renamed_paths": list(self.renamed_paths),
        }


@dataclass(frozen=True, slots=True)
class ChangeFinding:
    """How one path's declaration and observation reconcile."""

    path: str
    classification: str
    severity: str
    path_authority: str
    declared_change_kind: str | None = None
    observed_change_kind: str | None = None
    change_identity_sha256: str | None = None
    forbidden_reason: str | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _bounded_path(self.path, "change finding path")
        if self.classification not in CHANGE_CLASSIFICATIONS:
            raise ValueError(
                f"unsupported change classification: {self.classification!r}"
            )
        if self.severity not in SEVERITIES:
            raise ValueError(f"unsupported change severity: {self.severity!r}")
        if self.path_authority not in PATH_AUTHORITIES:
            raise ValueError(f"unsupported path authority: {self.path_authority!r}")
        for value, label in (
            (self.declared_change_kind, "declared change kind"),
            (self.observed_change_kind, "observed change kind"),
        ):
            if value is not None and value not in CHANGE_KINDS:
                raise ValueError(f"unsupported {label}: {value!r}")
        _require_sha256(
            self.change_identity_sha256, "change identity", optional=True
        )
        if (
            self.forbidden_reason is not None
            and self.forbidden_reason not in FORBIDDEN_REASONS
        ):
            raise ValueError("unsupported forbidden reason")
        _ordered_vocabulary(
            self.reason_codes, CHANGE_FINDING_REASONS, "change finding reasons"
        )
        if (
            self.classification == CLASSIFICATION_DECLARED_UNOBSERVED
            and self.observed_change_kind is not None
        ):
            raise ValueError(
                "a declared-but-unobserved change has no observed change kind"
            )
        if (
            self.classification == CLASSIFICATION_UNDECLARED
            and self.declared_change_kind is not None
        ):
            raise ValueError("an undeclared change has no declared change kind")

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "classification": self.classification,
            "severity": self.severity,
            "path_authority": self.path_authority,
            "declared_change_kind": self.declared_change_kind,
            "observed_change_kind": self.observed_change_kind,
            "change_identity_sha256": self.change_identity_sha256,
            "forbidden_reason": self.forbidden_reason,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """How one validation expectation, or one extra receipt, reconciles."""

    validation_id: str
    validation_kind: str
    required: bool
    coverage: str
    receipt_ids: tuple[str, ...] = ()
    receipt_result: str | None = None
    receipt_state_fingerprint: str | None = None
    expected_target_scope: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _bounded_identifier(self.validation_id, "validation finding id")
        if self.validation_kind not in VALIDATION_KINDS:
            raise ValueError(
                f"unsupported validation finding kind: {self.validation_kind!r}"
            )
        if not isinstance(self.required, bool):
            raise TypeError("validation finding required must be a bool")
        if self.coverage not in VALIDATION_COVERAGE_STATES:
            raise ValueError(f"unsupported validation coverage: {self.coverage!r}")
        _bounded_tuple(
            self.receipt_ids, MAX_VALIDATION_RECEIPTS, "validation finding receipts"
        )
        _validate_unique(self.receipt_ids, "validation finding receipt id")
        if tuple(sorted(self.receipt_ids)) != self.receipt_ids:
            raise ValueError("validation finding receipt ids must be sorted")
        if self.receipt_result is not None and self.receipt_result not in RECEIPT_RESULTS:
            raise ValueError("unsupported validation finding receipt result")
        _require_sha256(
            self.receipt_state_fingerprint,
            "validation finding receipt state",
            optional=True,
        )
        _canonical_paths(self.expected_target_scope, "validation finding scope")
        if tuple(sorted(self.expected_target_scope)) != self.expected_target_scope:
            raise ValueError("validation finding scope must be canonically sorted")
        _ordered_vocabulary(
            self.reason_codes,
            VALIDATION_FINDING_REASONS,
            "validation finding reasons",
        )
        if self.coverage == COVERAGE_ADDITIONAL_OBSERVED and self.required:
            raise ValueError("an additional observed validation is never required")

    def as_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "validation_kind": self.validation_kind,
            "required": self.required,
            "coverage": self.coverage,
            "receipt_ids": list(self.receipt_ids),
            "receipt_result": self.receipt_result,
            "receipt_state_fingerprint": self.receipt_state_fingerprint,
            "expected_target_scope": list(self.expected_target_scope),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class PreservationFinding:
    """One carried preservation obligation and whether a receipt certifies it."""

    obligation_id: str
    kind: str
    text_sha256: str
    state: str
    certifying_validation_id: str | None = None

    def __post_init__(self) -> None:
        _bounded_identifier(self.obligation_id, "preservation finding id")
        if self.kind not in PRESERVATION_OBLIGATION_KINDS:
            raise ValueError(f"unsupported preservation finding kind: {self.kind!r}")
        _require_sha256(self.text_sha256, "preservation finding text digest")
        if self.state not in PRESERVATION_OBLIGATION_STATES:
            raise ValueError(f"unsupported preservation state: {self.state!r}")
        _bounded_identifier(
            self.certifying_validation_id,
            "preservation finding certifying validation id",
            optional=True,
        )
        if self.state != OBLIGATION_UNRESOLVED and self.certifying_validation_id is None:
            raise ValueError(
                "a certified or failed-certification obligation names its validation"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "kind": self.kind,
            "text_sha256": self.text_sha256,
            "state": self.state,
            "certifying_validation_id": self.certifying_validation_id,
        }


@dataclass(frozen=True, slots=True)
class FinalStateBinding:
    """Which repository state the reconciliation and its receipts describe."""

    repository_id: str
    execution_run_id: str
    pre_execution_state_fingerprint: str
    post_execution_state_fingerprint: str
    final_state_fingerprint: str
    post_validation_state_fingerprint: str | None
    validation_coverage_complete: bool
    validated_state_current: bool

    def __post_init__(self) -> None:
        _bounded_identifier(self.repository_id, "final binding repository id")
        _bounded_identifier(self.execution_run_id, "final binding run id")
        _require_sha256(
            self.pre_execution_state_fingerprint, "final binding pre-execution state"
        )
        _require_sha256(
            self.post_execution_state_fingerprint, "final binding post-execution state"
        )
        _require_sha256(self.final_state_fingerprint, "final binding final state")
        _require_sha256(
            self.post_validation_state_fingerprint,
            "final binding post-validation state",
            optional=True,
        )
        for value, label in (
            (self.validation_coverage_complete, "validation_coverage_complete"),
            (self.validated_state_current, "validated_state_current"),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{label} must be a bool")

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository_id": self.repository_id,
            "execution_run_id": self.execution_run_id,
            "pre_execution_state_fingerprint": self.pre_execution_state_fingerprint,
            "post_execution_state_fingerprint": self.post_execution_state_fingerprint,
            "post_validation_state_fingerprint": (
                self.post_validation_state_fingerprint
            ),
            "final_state_fingerprint": self.final_state_fingerprint,
            "validation_coverage_complete": self.validation_coverage_complete,
            "validated_state_current": self.validated_state_current,
        }


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class PostRunReconciliation:
    """The bounded, deterministic post-run contract reconciliation."""

    status: str
    task_contract_fingerprint: str
    execution_authorization_fingerprint: str
    worker_report_fingerprint: str
    observed_facts_fingerprint: str
    request_fingerprint: str
    declared_change_summary: ChangeSummary
    observed_change_summary: ChangeSummary
    change_findings: tuple[ChangeFinding, ...]
    validation_findings: tuple[ValidationFinding, ...]
    preservation_findings: tuple[PreservationFinding, ...]
    worker_status_claim: str
    worker_status_consistent: bool
    final_state_binding: FinalStateBinding
    unresolved_requirements: tuple[str, ...]
    reasons: tuple[str, ...]
    inconsistencies: tuple[str, ...]
    facts_collected_externally: bool
    schema_version: str = RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in RECONCILIATION_STATUSES:
            raise ValueError(f"unsupported reconciliation status: {self.status!r}")
        _require_sha256(self.task_contract_fingerprint, "task contract fingerprint")
        _require_sha256(
            self.execution_authorization_fingerprint,
            "execution authorization fingerprint",
        )
        _require_sha256(self.worker_report_fingerprint, "worker report fingerprint")
        _require_sha256(self.observed_facts_fingerprint, "observed facts fingerprint")
        _require_sha256(self.request_fingerprint, "reconciliation request fingerprint")
        for value, label in (
            (self.declared_change_summary, "declared_change_summary"),
            (self.observed_change_summary, "observed_change_summary"),
        ):
            if type(value) is not ChangeSummary:
                raise TypeError(f"{label} must be a ChangeSummary")
        _bounded_tuple(self.change_findings, MAX_CHANGE_FINDINGS, "change findings")
        _bounded_tuple(
            self.validation_findings, MAX_VALIDATION_FINDINGS, "validation findings"
        )
        _bounded_tuple(
            self.preservation_findings,
            MAX_PRESERVATION_FINDINGS,
            "preservation findings",
        )
        if not all(type(item) is ChangeFinding for item in self.change_findings):
            raise TypeError("change_findings must contain ChangeFinding records")
        if not all(
            type(item) is ValidationFinding for item in self.validation_findings
        ):
            raise TypeError(
                "validation_findings must contain ValidationFinding records"
            )
        if not all(
            type(item) is PreservationFinding for item in self.preservation_findings
        ):
            raise TypeError(
                "preservation_findings must contain PreservationFinding records"
            )
        if self.worker_status_claim not in WORKER_STATUS_CLAIMS:
            raise ValueError("unsupported worker status claim")
        if not isinstance(self.worker_status_consistent, bool):
            raise TypeError("worker_status_consistent must be a bool")
        if type(self.final_state_binding) is not FinalStateBinding:
            raise TypeError("final_state_binding must be a FinalStateBinding")
        _ordered_vocabulary(
            self.unresolved_requirements,
            RECONCILIATION_UNRESOLVED_REQUIREMENTS,
            "unresolved requirements",
        )
        _ordered_vocabulary(
            self.reasons, RECONCILIATION_REASONS, "reconciliation reasons"
        )
        _ordered_vocabulary(
            self.inconsistencies,
            RECONCILIATION_INCONSISTENCIES,
            "reconciliation inconsistencies",
        )
        if not isinstance(self.facts_collected_externally, bool):
            raise TypeError("facts_collected_externally must be a bool")
        if self.status == STATUS_INCONSISTENT_INPUT and not self.inconsistencies:
            raise ValueError("an inconsistent fact set states an inconsistency")
        if UNRESOLVED_SEMANTIC_GOAL_REVIEW not in self.unresolved_requirements:
            raise ValueError(
                "every reconciliation leaves semantic goal review outstanding"
            )
        if UNRESOLVED_HUMAN_REVIEW not in self.unresolved_requirements:
            raise ValueError("every reconciliation leaves human review outstanding")
        if self.schema_version != RESULT_SCHEMA_VERSION:
            raise ValueError("unsupported post-run reconciliation schema version")

    # -- Named views over the single canonical finding list -------------------

    def _by_classification(self, classification: str) -> tuple[ChangeFinding, ...]:
        return tuple(
            item for item in self.change_findings if item.classification == classification
        )

    @property
    def matched_changes(self) -> tuple[ChangeFinding, ...]:
        return self._by_classification(CLASSIFICATION_MATCHED)

    @property
    def undeclared_changes(self) -> tuple[ChangeFinding, ...]:
        return self._by_classification(CLASSIFICATION_UNDECLARED)

    @property
    def declared_but_unobserved_changes(self) -> tuple[ChangeFinding, ...]:
        return self._by_classification(CLASSIFICATION_DECLARED_UNOBSERVED)

    @property
    def forbidden_changes(self) -> tuple[ChangeFinding, ...]:
        return tuple(
            item
            for item in self.change_findings
            if item.path_authority == PATH_AUTHORITY_FORBIDDEN
            and item.observed_change_kind is not None
        )

    @property
    def out_of_scope_changes(self) -> tuple[ChangeFinding, ...]:
        return tuple(
            item
            for item in self.change_findings
            if item.path_authority
            in {
                PATH_AUTHORITY_UNAUTHORIZED,
                PATH_AUTHORITY_SUPPORTING_READ_ONLY,
                PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY,
            }
            and item.observed_change_kind is not None
        )

    def _validation_by_coverage(self, *coverage: str) -> tuple[ValidationFinding, ...]:
        wanted = set(coverage)
        return tuple(
            item for item in self.validation_findings if item.coverage in wanted
        )

    @property
    def validation_expected(self) -> tuple[ValidationFinding, ...]:
        return tuple(
            item
            for item in self.validation_findings
            if item.coverage != COVERAGE_ADDITIONAL_OBSERVED
        )

    @property
    def validation_observed(self) -> tuple[ValidationFinding, ...]:
        return tuple(item for item in self.validation_findings if item.receipt_ids)

    @property
    def validation_satisfied(self) -> tuple[ValidationFinding, ...]:
        return self._validation_by_coverage(COVERAGE_SATISFIED)

    @property
    def validation_missing(self) -> tuple[ValidationFinding, ...]:
        return self._validation_by_coverage(COVERAGE_MISSING, COVERAGE_OPTIONAL_MISSING)

    @property
    def validation_stale(self) -> tuple[ValidationFinding, ...]:
        return self._validation_by_coverage(COVERAGE_STALE)

    @property
    def validation_failed(self) -> tuple[ValidationFinding, ...]:
        return self._validation_by_coverage(COVERAGE_FAILED)

    @property
    def additional_validation_observed(self) -> tuple[ValidationFinding, ...]:
        return self._validation_by_coverage(COVERAGE_ADDITIONAL_OBSERVED)

    # -- Authority ------------------------------------------------------------

    @property
    def post_run_reconciliation_authority(self) -> bool:
        return self.status != STATUS_INCONSISTENT_INPUT

    @property
    def semantic_goal_review_authority(self) -> bool:
        return False

    @property
    def implementation_correctness_authority(self) -> bool:
        return False

    @property
    def final_success_authority(self) -> bool:
        return False

    @property
    def check_2_required(self) -> bool:
        """CHECK.1 never discharges semantic goal review."""
        return True

    def _identity(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "status": self.status,
            "task_contract_fingerprint": self.task_contract_fingerprint,
            "execution_authorization_fingerprint": (
                self.execution_authorization_fingerprint
            ),
            "worker_report_fingerprint": self.worker_report_fingerprint,
            "observed_facts_fingerprint": self.observed_facts_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "declared_change_summary": self.declared_change_summary.as_dict(),
            "observed_change_summary": self.observed_change_summary.as_dict(),
            "change_findings": [item.as_dict() for item in self.change_findings],
            "validation_findings": [
                item.as_dict() for item in self.validation_findings
            ],
            "preservation_findings": [
                item.as_dict() for item in self.preservation_findings
            ],
            "worker_status_claim": self.worker_status_claim,
            "worker_status_consistent": self.worker_status_consistent,
            "final_state_binding": self.final_state_binding.as_dict(),
            "unresolved_requirements": list(self.unresolved_requirements),
            "reasons": list(self.reasons),
            "inconsistencies": list(self.inconsistencies),
            "facts_collected_externally": self.facts_collected_externally,
        }

    @property
    def reconciliation_fingerprint(self) -> str:
        return _fingerprint(self._identity())

    def as_dict(self) -> dict[str, Any]:
        payload = self._identity()
        payload["views"] = {
            "matched_changes": [item.path for item in self.matched_changes],
            "undeclared_changes": [item.path for item in self.undeclared_changes],
            "declared_but_unobserved_changes": [
                item.path for item in self.declared_but_unobserved_changes
            ],
            "forbidden_changes": [item.path for item in self.forbidden_changes],
            "out_of_scope_changes": [item.path for item in self.out_of_scope_changes],
            "validation_expected": [
                item.validation_id for item in self.validation_expected
            ],
            "validation_observed": [
                item.validation_id for item in self.validation_observed
            ],
            "validation_missing": [
                item.validation_id for item in self.validation_missing
            ],
            "validation_stale": [item.validation_id for item in self.validation_stale],
            "validation_failed": [
                item.validation_id for item in self.validation_failed
            ],
            "additional_validation_observed": [
                item.validation_id for item in self.additional_validation_observed
            ],
        }
        payload["reconciled_meaning"] = RECONCILED_MEANING
        payload["reconciliation_fingerprint"] = self.reconciliation_fingerprint
        payload["authority"] = reconciliation_authority(
            post_run_reconciliation_authority=self.post_run_reconciliation_authority
        )
        payload["guardrails"] = reconciliation_guardrails(
            worker_report_reconciled=CHECK_WORKER_REPORT_BOUND in self.reasons,
            change_scope_checked=CHECK_CHANGE_SCOPE_CHECKED in self.reasons,
            declared_vs_observed_compared=(
                CHECK_DECLARED_VS_OBSERVED_COMPARED in self.reasons
            ),
            validation_receipts_checked=(
                CHECK_VALIDATION_RECEIPTS_CHECKED in self.reasons
            ),
            validation_freshness_checked=(
                CHECK_VALIDATION_FRESHNESS_CHECKED in self.reasons
            ),
            final_state_binding_checked=(
                CHECK_FINAL_STATE_BINDING_CHECKED in self.reasons
            ),
            facts_collected_externally=self.facts_collected_externally,
        )
        return payload


# ── Authority and guardrails ──────────────────────────────────────────────────

def reconciliation_authority(
    *, post_run_reconciliation_authority: bool
) -> dict[str, bool]:
    """Exactly one narrow authority; every other power is denied."""
    return {
        "post_run_reconciliation_authority": post_run_reconciliation_authority,
        "semantic_goal_review_authority": False,
        "implementation_correctness_authority": False,
        "final_success_authority": False,
        "merge_authority": False,
        "patch_authority": False,
        "write_authority": False,
        "repository_read_authority": False,
        "repository_traversal_authority": False,
        "validation_execution_authority": False,
        "command_execution_authority": False,
        "model_selection_authority": False,
        "provider_selection_authority": False,
        "final_response_authority": False,
        "human_approval_required": True,
    }


def reconciliation_guardrails(
    *,
    worker_report_reconciled: bool,
    change_scope_checked: bool,
    declared_vs_observed_compared: bool,
    validation_receipts_checked: bool,
    validation_freshness_checked: bool,
    final_state_binding_checked: bool,
    facts_collected_externally: bool,
) -> dict[str, bool]:
    return {
        "worker_report_reconciled": worker_report_reconciled,
        "change_scope_checked": change_scope_checked,
        "declared_vs_observed_compared": declared_vs_observed_compared,
        "validation_receipts_checked": validation_receipts_checked,
        "validation_freshness_checked": validation_freshness_checked,
        "final_state_binding_checked": final_state_binding_checked,
        "facts_collected_externally": facts_collected_externally,
        "repository_traversed": False,
        "source_content_read": False,
        "validation_executed": False,
        "patch_applied": False,
        "files_modified": False,
        "semantic_goal_review_performed": False,
        "model_called": False,
        "conflict_resolved": False,
        "merge_performed": False,
        "final_success_declared": False,
    }


# ── Reconciliation ────────────────────────────────────────────────────────────

def _change_summary(
    kinds: dict[str, str],
) -> ChangeSummary:
    """Build a path summary from a path -> change-kind mapping."""
    buckets: dict[str, list[str]] = {kind: [] for kind in CHANGE_KINDS}
    for path, kind in kinds.items():
        buckets[kind].append(path)
    return ChangeSummary(
        added_paths=tuple(sorted(buckets[CHANGE_ADDED])),
        deleted_paths=tuple(sorted(buckets[CHANGE_DELETED])),
        modified_paths=tuple(sorted(buckets[CHANGE_MODIFIED])),
        renamed_paths=tuple(sorted(buckets[CHANGE_RENAMED])),
    )


def _authority_index(
    authorization: ExecutionAuthorization,
) -> tuple[dict[str, AuthorizedPath], frozenset[str]]:
    """Index authorized paths, applying bounded expansion receipts.

    An expansion receipt may widen the authorized set but can never reach a
    path the authorization marked forbidden: forbidden always wins.
    """
    index = {item.path: item for item in authorization.authorized_paths}
    expanded: set[str] = set()
    for receipt in authorization.path_expansion_receipts:
        existing = index.get(receipt.path)
        if existing is not None and existing.authority == PATH_AUTHORITY_FORBIDDEN:
            continue
        index[receipt.path] = AuthorizedPath(
            path=receipt.path,
            authority=receipt.authority,
            worker_id=(existing.worker_id if existing is not None else None),
        )
        expanded.add(receipt.path)
    return index, frozenset(expanded)


def _path_authority_codes(
    entry: AuthorizedPath | None,
    *,
    expanded: bool,
    report_worker_id: str | None,
    ownership_declared: bool,
) -> tuple[str, str | None, set[str], bool, str | None]:
    """Resolve one path's authority, its finding codes and its severity floor.

    Returns ``(authority, forbidden_reason, codes, write_allowed,
    scope_inconsistency)``.
    """
    codes: set[str] = set()
    if entry is None:
        codes.add(FINDING_OUTSIDE_AUTHORIZED_SCOPE)
        codes.add(FINDING_WRITE_NOT_AUTHORIZED)
        return (
            PATH_AUTHORITY_UNAUTHORIZED,
            None,
            codes,
            False,
            INCONSISTENT_OUT_OF_SCOPE_CHANGE,
        )

    if expanded:
        codes.add(FINDING_PATH_EXPANSION_APPLIED)

    if entry.authority == PATH_AUTHORITY_FORBIDDEN:
        codes.add(FINDING_FORBIDDEN_PATH)
        codes.add(FINDING_WRITE_NOT_AUTHORIZED)
        return (
            entry.authority,
            entry.forbidden_reason,
            codes,
            False,
            INCONSISTENT_FORBIDDEN_CHANGE,
        )
    if entry.authority == PATH_AUTHORITY_SUPPORTING_READ_ONLY:
        codes.add(FINDING_SUPPORTING_READ_ONLY)
        codes.add(FINDING_WRITE_NOT_AUTHORIZED)
        return (
            entry.authority,
            None,
            codes,
            False,
            INCONSISTENT_SUPPORTING_FILE_WRITTEN,
        )
    if entry.authority == PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY:
        codes.add(FINDING_VALIDATION_EXECUTE_ONLY)
        codes.add(FINDING_WRITE_NOT_AUTHORIZED)
        return (
            entry.authority,
            None,
            codes,
            False,
            INCONSISTENT_VALIDATION_FILE_WRITTEN,
        )

    codes.add(FINDING_WRITE_AUTHORIZED)
    if entry.authority == PATH_AUTHORITY_WRITABLE_WITH_REVIEW:
        codes.add(FINDING_REVIEW_REQUIRED)

    if (
        ownership_declared
        and entry.worker_id is not None
        and report_worker_id is not None
        and entry.worker_id != report_worker_id
    ):
        codes.add(FINDING_WORKER_SCOPE)
        return (entry.authority, None, codes, False, INCONSISTENT_WORKER_SCOPE)

    return (entry.authority, None, codes, True, None)


def _reconcile_changes(
    authorization: ExecutionAuthorization,
    report: WorkerReport,
    facts: ObservedPostRunFacts,
) -> tuple[tuple[ChangeFinding, ...], set[str]]:
    index, expanded = _authority_index(authorization)
    ownership_declared = authorization.declares_worker_ownership
    declared = {item.path: item for item in report.declared_changes}
    observed = {item.path: item for item in facts.observed_changes}
    inconsistencies: set[str] = set()
    findings: list[ChangeFinding] = []

    for path in sorted(set(observed) | set(declared)):
        observed_change = observed.get(path)
        declared_change = declared.get(path)
        entry = index.get(path)

        if observed_change is None:
            # Declared but never observed.  The observed set is authoritative:
            # no diff is fabricated to match the declaration.
            authority, forbidden_reason, codes, _write, _scope = _path_authority_codes(
                entry,
                expanded=path in expanded,
                report_worker_id=report.worker_id,
                ownership_declared=ownership_declared,
            )
            codes.add(FINDING_DECLARED)
            codes.add(FINDING_NOT_OBSERVED)
            # A path that was never written cannot violate write authority.
            codes.discard(FINDING_WRITE_NOT_AUTHORIZED)
            codes.discard(FINDING_OUTSIDE_AUTHORIZED_SCOPE)
            codes.discard(FINDING_WORKER_SCOPE)
            inconsistencies.add(INCONSISTENT_DECLARED_UNOBSERVED)
            findings.append(
                ChangeFinding(
                    path=path,
                    classification=CLASSIFICATION_DECLARED_UNOBSERVED,
                    severity=SEVERITY_SUSPICIOUS,
                    path_authority=authority,
                    declared_change_kind=declared_change.change_kind,
                    forbidden_reason=forbidden_reason,
                    reason_codes=_ordered_codes(codes, CHANGE_FINDING_REASONS),
                )
            )
            continue

        authority, forbidden_reason, codes, write_allowed, scope_code = (
            _path_authority_codes(
                entry,
                expanded=path in expanded,
                report_worker_id=report.worker_id,
                ownership_declared=ownership_declared,
            )
        )
        if scope_code is not None:
            inconsistencies.add(scope_code)

        if declared_change is None:
            codes.add(FINDING_UNDECLARED)
            inconsistencies.add(INCONSISTENT_UNDECLARED_CHANGE)
            severity = SEVERITY_BLOCKED if not write_allowed else SEVERITY_SUSPICIOUS
            findings.append(
                ChangeFinding(
                    path=path,
                    classification=CLASSIFICATION_UNDECLARED,
                    severity=severity,
                    path_authority=authority,
                    observed_change_kind=observed_change.change_kind,
                    change_identity_sha256=observed_change.change_identity_sha256,
                    forbidden_reason=forbidden_reason,
                    reason_codes=_ordered_codes(codes, CHANGE_FINDING_REASONS),
                )
            )
            continue

        codes.add(FINDING_DECLARED)
        classification = CLASSIFICATION_MATCHED
        severity = SEVERITY_BLOCKED if not write_allowed else SEVERITY_INFORMATIONAL

        if declared_change.change_kind != observed_change.change_kind or (
            declared_change.from_path != observed_change.from_path
        ):
            classification = CLASSIFICATION_KIND_MISMATCH
            codes.add(FINDING_KIND_MISMATCH)
            inconsistencies.add(INCONSISTENT_DECLARED_KIND)
            if severity != SEVERITY_BLOCKED:
                severity = SEVERITY_SUSPICIOUS
        elif (
            declared_change.expected_change_identity_sha256 is not None
            and declared_change.expected_change_identity_sha256
            != observed_change.change_identity_sha256
        ):
            classification = CLASSIFICATION_IDENTITY_MISMATCH
            codes.add(FINDING_IDENTITY_MISMATCH)
            inconsistencies.add(INCONSISTENT_DECLARED_IDENTITY)
            if severity != SEVERITY_BLOCKED:
                severity = SEVERITY_SUSPICIOUS

        findings.append(
            ChangeFinding(
                path=path,
                classification=classification,
                severity=severity,
                path_authority=authority,
                declared_change_kind=declared_change.change_kind,
                observed_change_kind=observed_change.change_kind,
                change_identity_sha256=observed_change.change_identity_sha256,
                forbidden_reason=forbidden_reason,
                reason_codes=_ordered_codes(codes, CHANGE_FINDING_REASONS),
            )
        )

    if not report.declared_changes and facts.observed_changes:
        inconsistencies.add(INCONSISTENT_NO_CHANGE_CLAIM)
    if report.declared_changes and not facts.observed_changes:
        inconsistencies.add(INCONSISTENT_CHANGE_CLAIM_WITHOUT_CHANGES)

    return tuple(findings), inconsistencies


def _receipt_matches_expectation(
    receipt: ValidationReceipt,
    expectation: ValidationExpectation,
    authorization: ExecutionAuthorization,
) -> str | None:
    """Return a rejection reason, or ``None`` when the receipt is usable."""
    if (
        receipt.validation_kind != expectation.validation_kind
        or receipt.execution_run_id != authorization.execution_run_id
        or receipt.repository_id != authorization.repository_id
    ):
        return VALIDATION_REASON_RECEIPT_INVALID
    if (
        expectation.expected_state_fingerprint is not None
        and receipt.state_fingerprint != expectation.expected_state_fingerprint
    ):
        return VALIDATION_REASON_RECEIPT_INVALID
    if receipt.target_scope != expectation.target_scope:
        return VALIDATION_REASON_SCOPE_MISMATCH
    return None


def _claimed_validation_ids(report: WorkerReport) -> set[str]:
    return {
        action.validation_id
        for action in report.declared_validation_actions
        if action.validation_id is not None
        and action.declared_result == DECLARED_VALIDATION_PASSED
    }


def _reconcile_validation(
    authorization: ExecutionAuthorization,
    report: WorkerReport,
    facts: ObservedPostRunFacts,
) -> tuple[tuple[ValidationFinding, ...], set[str], bool, bool, set[str]]:
    """Reconcile expectations against receipts.

    Returns ``(findings, inconsistencies, coverage_complete,
    validated_state_current, satisfied_validation_ids)``.
    """
    inconsistencies: set[str] = set()
    findings: list[ValidationFinding] = []
    claimed = _claimed_validation_ids(report)
    consumed_receipt_ids: set[str] = set()
    satisfied_ids: set[str] = set()
    coverage_complete = True
    current_states: list[bool] = []

    for expectation in sorted(
        authorization.validation_expectations, key=lambda item: item.validation_id
    ):
        candidates = [
            receipt
            for receipt in facts.validation_receipts
            if receipt.validation_id == expectation.validation_id
        ]
        for receipt in candidates:
            consumed_receipt_ids.add(receipt.receipt_id)
        codes: set[str] = set()
        if not candidates:
            codes.add(VALIDATION_REASON_NO_RECEIPT)
            if expectation.validation_id in claimed:
                codes.add(VALIDATION_REASON_UNVERIFIED_CLAIM)
                inconsistencies.add(INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM)
            if expectation.required:
                coverage = COVERAGE_MISSING
                coverage_complete = False
                inconsistencies.add(INCONSISTENT_VALIDATION_MISSING)
            else:
                coverage = COVERAGE_OPTIONAL_MISSING
                codes.add(VALIDATION_REASON_OPTIONAL)
            findings.append(
                ValidationFinding(
                    validation_id=expectation.validation_id,
                    validation_kind=expectation.validation_kind,
                    required=expectation.required,
                    coverage=coverage,
                    expected_target_scope=expectation.target_scope,
                    reason_codes=_ordered_codes(codes, VALIDATION_FINDING_REASONS),
                )
            )
            continue

        usable: list[ValidationReceipt] = []
        rejections: set[str] = set()
        for receipt in candidates:
            rejection = _receipt_matches_expectation(
                receipt, expectation, authorization
            )
            if rejection is None:
                usable.append(receipt)
            else:
                rejections.add(rejection)

        receipt_ids = tuple(sorted(item.receipt_id for item in candidates))

        if not usable:
            codes |= rejections
            if VALIDATION_REASON_SCOPE_MISMATCH in rejections:
                coverage = COVERAGE_SCOPE_MISMATCH
                inconsistencies.add(INCONSISTENT_VALIDATION_SCOPE)
            else:
                coverage = COVERAGE_RECEIPT_INVALID
                inconsistencies.add(INCONSISTENT_VALIDATION_RECEIPT_INVALID)
            if expectation.required:
                coverage_complete = False
            else:
                codes.add(VALIDATION_REASON_OPTIONAL)
            findings.append(
                ValidationFinding(
                    validation_id=expectation.validation_id,
                    validation_kind=expectation.validation_kind,
                    required=expectation.required,
                    coverage=coverage,
                    receipt_ids=receipt_ids,
                    expected_target_scope=expectation.target_scope,
                    reason_codes=_ordered_codes(codes, VALIDATION_FINDING_REASONS),
                )
            )
            continue

        failing = [item for item in usable if item.result in _FAILING_RECEIPT_RESULTS]
        passing = [item for item in usable if item.result == RECEIPT_PASSED]
        usable_ids = tuple(sorted(item.receipt_id for item in usable))

        if failing:
            codes.add(VALIDATION_REASON_RESULT_FAILED)
            inconsistencies.add(INCONSISTENT_VALIDATION_FAILED)
            if expectation.required:
                coverage_complete = False
            else:
                codes.add(VALIDATION_REASON_OPTIONAL)
            findings.append(
                ValidationFinding(
                    validation_id=expectation.validation_id,
                    validation_kind=expectation.validation_kind,
                    required=expectation.required,
                    coverage=COVERAGE_FAILED,
                    receipt_ids=usable_ids,
                    receipt_result=sorted(item.result for item in failing)[0],
                    receipt_state_fingerprint=sorted(
                        item.state_fingerprint for item in failing
                    )[0],
                    expected_target_scope=expectation.target_scope,
                    reason_codes=_ordered_codes(codes, VALIDATION_FINDING_REASONS),
                )
            )
            continue

        if not passing:
            # Only skipped receipts: a skip is not an execution.
            codes.add(VALIDATION_REASON_SKIPPED)
            codes.add(VALIDATION_REASON_NO_RECEIPT)
            if expectation.validation_id in claimed:
                codes.add(VALIDATION_REASON_UNVERIFIED_CLAIM)
                inconsistencies.add(INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM)
            if expectation.required:
                coverage = COVERAGE_MISSING
                coverage_complete = False
                inconsistencies.add(INCONSISTENT_VALIDATION_MISSING)
            else:
                coverage = COVERAGE_OPTIONAL_MISSING
                codes.add(VALIDATION_REASON_OPTIONAL)
            findings.append(
                ValidationFinding(
                    validation_id=expectation.validation_id,
                    validation_kind=expectation.validation_kind,
                    required=expectation.required,
                    coverage=coverage,
                    receipt_ids=usable_ids,
                    receipt_result=RECEIPT_SKIPPED,
                    expected_target_scope=expectation.target_scope,
                    reason_codes=_ordered_codes(codes, VALIDATION_FINDING_REASONS),
                )
            )
            continue

        current = [
            item
            for item in passing
            if item.state_fingerprint == facts.final_state_fingerprint
        ]
        if current:
            codes.add(VALIDATION_REASON_CURRENT)
            if not expectation.required:
                codes.add(VALIDATION_REASON_OPTIONAL)
            satisfied_ids.add(expectation.validation_id)
            if expectation.required:
                current_states.append(True)
            findings.append(
                ValidationFinding(
                    validation_id=expectation.validation_id,
                    validation_kind=expectation.validation_kind,
                    required=expectation.required,
                    coverage=COVERAGE_SATISFIED,
                    receipt_ids=usable_ids,
                    receipt_result=RECEIPT_PASSED,
                    receipt_state_fingerprint=facts.final_state_fingerprint,
                    expected_target_scope=expectation.target_scope,
                    reason_codes=_ordered_codes(codes, VALIDATION_FINDING_REASONS),
                )
            )
            continue

        # Passing, but bound to a state that is no longer the final state.
        codes.add(VALIDATION_REASON_STALE)
        inconsistencies.add(INCONSISTENT_VALIDATION_STALE)
        if expectation.required:
            coverage_complete = False
            current_states.append(False)
        else:
            codes.add(VALIDATION_REASON_OPTIONAL)
        findings.append(
            ValidationFinding(
                validation_id=expectation.validation_id,
                validation_kind=expectation.validation_kind,
                required=expectation.required,
                coverage=COVERAGE_STALE,
                receipt_ids=usable_ids,
                receipt_result=RECEIPT_PASSED,
                receipt_state_fingerprint=sorted(
                    item.state_fingerprint for item in passing
                )[0],
                expected_target_scope=expectation.target_scope,
                reason_codes=_ordered_codes(codes, VALIDATION_FINDING_REASONS),
            )
        )

    # Receipts nobody asked for are recorded, never used to discharge anything.
    for receipt in sorted(facts.validation_receipts, key=lambda item: item.receipt_id):
        if receipt.receipt_id in consumed_receipt_ids:
            continue
        findings.append(
            ValidationFinding(
                validation_id=receipt.validation_id,
                validation_kind=receipt.validation_kind,
                required=False,
                coverage=COVERAGE_ADDITIONAL_OBSERVED,
                receipt_ids=(receipt.receipt_id,),
                receipt_result=receipt.result,
                receipt_state_fingerprint=receipt.state_fingerprint,
                reason_codes=(VALIDATION_REASON_ADDITIONAL,),
            )
        )

    # A worker validation claim with no receipt at all cannot mint a receipt.
    expectation_ids = {
        item.validation_id for item in authorization.validation_expectations
    }
    receipt_index = {
        (item.validation_id, item.validation_kind, item.result)
        for item in facts.validation_receipts
    }
    receipt_kinds = {
        (item.validation_kind, item.result) for item in facts.validation_receipts
    }
    for action in report.declared_validation_actions:
        if action.declared_result != DECLARED_VALIDATION_PASSED:
            continue
        if action.validation_id is not None:
            if action.validation_id in expectation_ids:
                continue  # already resolved against its expectation above
            if (
                action.validation_id,
                action.validation_kind,
                RECEIPT_PASSED,
            ) not in receipt_index:
                inconsistencies.add(INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM)
        elif (action.validation_kind, RECEIPT_PASSED) not in receipt_kinds:
            inconsistencies.add(INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM)

    if (
        facts.post_validation_state_fingerprint is not None
        and facts.post_validation_state_fingerprint != facts.final_state_fingerprint
    ):
        inconsistencies.add(INCONSISTENT_POST_VALIDATION_MUTATION)

    validated_state_current = bool(current_states) and all(current_states)
    return (
        tuple(findings),
        inconsistencies,
        coverage_complete,
        validated_state_current,
        satisfied_ids,
    )


def _reconcile_preservation(
    authorization: ExecutionAuthorization,
    satisfied_validation_ids: set[str],
) -> tuple[tuple[PreservationFinding, ...], bool]:
    findings: list[PreservationFinding] = []
    any_unresolved = False
    for obligation in sorted(
        authorization.preservation_obligations, key=lambda item: item.obligation_id
    ):
        if obligation.certifying_validation_id is None:
            state = OBLIGATION_UNRESOLVED
            any_unresolved = True
        elif obligation.certifying_validation_id in satisfied_validation_ids:
            state = OBLIGATION_CERTIFIED
        else:
            state = OBLIGATION_CERTIFICATION_UNSATISFIED
            any_unresolved = True
        findings.append(
            PreservationFinding(
                obligation_id=obligation.obligation_id,
                kind=obligation.kind,
                text_sha256=obligation.text_sha256,
                state=state,
                certifying_validation_id=obligation.certifying_validation_id,
            )
        )
    return tuple(findings), any_unresolved


def _input_inconsistencies(
    request: PostRunReconciliationRequest,
) -> tuple[set[str], str, str, str]:
    """Re-derive every binding and detect a tampered or incoherent fact set."""
    authorization = request.authorization
    report = request.worker_report
    facts = request.observed_facts
    codes: set[str] = set()

    authorization_fingerprint = execution_authorization_fingerprint(authorization)
    report_fingerprint = worker_report_fingerprint(report)
    facts_fingerprint = observed_post_run_facts_fingerprint(facts)

    if authorization_fingerprint != request.expected_authorization_fingerprint:
        codes.add(INCONSISTENT_AUTHORIZATION_FINGERPRINT)
    if report_fingerprint != request.expected_worker_report_fingerprint:
        codes.add(INCONSISTENT_WORKER_REPORT_FINGERPRINT)
    if facts_fingerprint != request.expected_observed_facts_fingerprint:
        codes.add(INCONSISTENT_OBSERVED_FACTS_FINGERPRINT)
    if (
        authorization.task_contract_fingerprint
        != request.expected_task_contract_fingerprint
    ):
        codes.add(INCONSISTENT_TASK_CONTRACT_FINGERPRINT)

    if request.expected_validation_receipt_fingerprints:
        derived = tuple(
            sorted(
                validation_receipt_fingerprint(item)
                for item in facts.validation_receipts
            )
        )
        if derived != request.expected_validation_receipt_fingerprints:
            codes.add(INCONSISTENT_VALIDATION_RECEIPT_FINGERPRINT)

    if not (
        authorization.execution_run_id
        == report.execution_run_id
        == facts.execution_run_id
    ):
        codes.add(INCONSISTENT_RUN_IDENTITY)
    if (
        authorization.worker_id is not None
        and report.worker_id is not None
        and authorization.worker_id != report.worker_id
    ):
        codes.add(INCONSISTENT_RUN_IDENTITY)
    if authorization.repository_id != facts.repository_id:
        codes.add(INCONSISTENT_REPOSITORY_IDENTITY)
    for receipt in facts.validation_receipts:
        if receipt.repository_id != authorization.repository_id:
            codes.add(INCONSISTENT_REPOSITORY_IDENTITY)

    if (
        authorization.pre_execution_state_fingerprint
        != facts.pre_execution_state_fingerprint
    ):
        codes.add(INCONSISTENT_STATE_CHAIN)
    if facts.observed_changes and (
        facts.pre_execution_state_fingerprint
        == facts.post_execution_state_fingerprint
    ):
        codes.add(INCONSISTENT_STATE_CHAIN)
    if not facts.observed_changes and (
        facts.pre_execution_state_fingerprint
        != facts.post_execution_state_fingerprint
    ):
        codes.add(INCONSISTENT_STATE_CHAIN)

    if not facts.rename_detection_supported and any(
        item.change_kind == CHANGE_RENAMED for item in facts.observed_changes
    ):
        codes.add(INCONSISTENT_RENAME_UNSUPPORTED)

    forbidden_paths = {
        item.path
        for item in authorization.authorized_paths
        if item.authority == PATH_AUTHORITY_FORBIDDEN
    }
    if any(
        item.path in forbidden_paths
        for item in authorization.path_expansion_receipts
    ):
        codes.add(INCONSISTENT_EXPANSION_OVER_FORBIDDEN)

    return codes, authorization_fingerprint, report_fingerprint, facts_fingerprint


def _worker_status_consistent(
    claim: str,
    *,
    blocked_present: bool,
    coverage_complete: bool,
    stale_present: bool,
    undeclared_present: bool,
    unobserved_present: bool,
    unverified_claim: bool,
    kind_or_identity_mismatch: bool,
) -> bool:
    """Derive whether the worker's own status claim survives the facts."""
    if claim == WORKER_CLAIM_SUCCESS:
        return not (
            blocked_present
            or not coverage_complete
            or stale_present
            or undeclared_present
            or unobserved_present
            or unverified_claim
            or kind_or_identity_mismatch
        )
    if claim == WORKER_CLAIM_PARTIAL:
        return not blocked_present
    # A failed or blocked claim under-claims; only a scope violation
    # contradicts it, and that is already recorded as a blocked finding.
    return not blocked_present


def reconcile_post_run(
    request: PostRunReconciliationRequest,
) -> PostRunReconciliation:
    """Reconcile one execution unit's contract, report and observed facts.

    The result states whether the execution stayed inside its contract.  It
    never states whether the implementation is correct, and it always leaves
    semantic goal review (CHECK.2) and human review outstanding.
    """
    if type(request) is not PostRunReconciliationRequest:
        raise TypeError(
            "reconcile_post_run requires an exact PostRunReconciliationRequest"
        )

    authorization = request.authorization
    report = request.worker_report
    facts = request.observed_facts

    (
        input_codes,
        authorization_fingerprint,
        report_fingerprint,
        facts_fingerprint,
    ) = _input_inconsistencies(request)

    declared_summary = _change_summary(
        {item.path: item.change_kind for item in report.declared_changes}
    )
    observed_summary = _change_summary(
        {item.path: item.change_kind for item in facts.observed_changes}
    )
    request_fingerprint = reconciliation_request_fingerprint(request)

    reasons: set[str] = {
        CHECK_AUTHORIZATION_BOUND,
        CHECK_WORKER_REPORT_BOUND,
        CHECK_OBSERVED_FACTS_BOUND,
        CHECK_NO_SEMANTIC_REVIEW_PERFORMED,
    }

    if input_codes & _INPUT_INCONSISTENCIES:
        binding = FinalStateBinding(
            repository_id=facts.repository_id,
            execution_run_id=facts.execution_run_id,
            pre_execution_state_fingerprint=facts.pre_execution_state_fingerprint,
            post_execution_state_fingerprint=facts.post_execution_state_fingerprint,
            final_state_fingerprint=facts.final_state_fingerprint,
            post_validation_state_fingerprint=(
                facts.post_validation_state_fingerprint
            ),
            validation_coverage_complete=False,
            validated_state_current=False,
        )
        return PostRunReconciliation(
            status=STATUS_INCONSISTENT_INPUT,
            task_contract_fingerprint=authorization.task_contract_fingerprint,
            execution_authorization_fingerprint=authorization_fingerprint,
            worker_report_fingerprint=report_fingerprint,
            observed_facts_fingerprint=facts_fingerprint,
            request_fingerprint=request_fingerprint,
            declared_change_summary=declared_summary,
            observed_change_summary=observed_summary,
            change_findings=(),
            validation_findings=(),
            preservation_findings=(),
            worker_status_claim=report.declared_status,
            worker_status_consistent=False,
            final_state_binding=binding,
            unresolved_requirements=_ordered_codes(
                {
                    UNRESOLVED_SEMANTIC_GOAL_REVIEW,
                    UNRESOLVED_UPSTREAM_INPUT,
                    UNRESOLVED_HUMAN_REVIEW,
                },
                RECONCILIATION_UNRESOLVED_REQUIREMENTS,
            ),
            reasons=_ordered_codes(reasons, RECONCILIATION_REASONS),
            inconsistencies=_ordered_codes(
                input_codes, RECONCILIATION_INCONSISTENCIES
            ),
            facts_collected_externally=facts.facts_collected_externally,
        )

    change_findings, change_codes = _reconcile_changes(authorization, report, facts)
    reasons |= {
        CHECK_DECLARED_VS_OBSERVED_COMPARED,
        CHECK_CHANGE_SCOPE_CHECKED,
        CHECK_FORBIDDEN_PATHS_CHECKED,
        CHECK_WORKER_STATUS_CLAIM_COMPARED,
        CHECK_FINAL_STATE_BINDING_CHECKED,
    }

    (
        validation_findings,
        validation_codes,
        coverage_complete,
        validated_state_current,
        satisfied_ids,
    ) = _reconcile_validation(authorization, report, facts)
    if authorization.validation_expectations:
        reasons.add(CHECK_VALIDATION_EXPECTATIONS_COMPARED)
    if facts.validation_receipts:
        reasons.add(CHECK_VALIDATION_RECEIPTS_CHECKED)
        reasons.add(CHECK_VALIDATION_FRESHNESS_CHECKED)

    preservation_findings, preservation_unresolved = _reconcile_preservation(
        authorization, satisfied_ids
    )
    if authorization.preservation_obligations:
        reasons.add(CHECK_PRESERVATION_OBLIGATIONS_CARRIED)

    inconsistencies = set(input_codes) | change_codes | validation_codes

    blocked_present = any(
        item.severity == SEVERITY_BLOCKED for item in change_findings
    ) or bool(inconsistencies & _BLOCKING_INCONSISTENCIES)
    suspicious_present = any(
        item.severity == SEVERITY_SUSPICIOUS for item in change_findings
    )
    stale_present = any(
        item.coverage == COVERAGE_STALE and item.required
        for item in validation_findings
    )
    undeclared_present = any(
        item.classification == CLASSIFICATION_UNDECLARED for item in change_findings
    )
    unobserved_present = any(
        item.classification == CLASSIFICATION_DECLARED_UNOBSERVED
        for item in change_findings
    )
    mismatch_present = any(
        item.classification
        in {CLASSIFICATION_KIND_MISMATCH, CLASSIFICATION_IDENTITY_MISMATCH}
        for item in change_findings
    )
    unverified_claim = INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM in inconsistencies

    worker_status_consistent = _worker_status_consistent(
        report.declared_status,
        blocked_present=blocked_present,
        coverage_complete=coverage_complete,
        stale_present=stale_present,
        undeclared_present=undeclared_present,
        unobserved_present=unobserved_present,
        unverified_claim=unverified_claim,
        kind_or_identity_mismatch=mismatch_present,
    )
    if not worker_status_consistent:
        if report.declared_status == WORKER_CLAIM_SUCCESS:
            inconsistencies.add(INCONSISTENT_WORKER_SUCCESS_CLAIM)
        else:
            inconsistencies.add(INCONSISTENT_WORKER_STATUS_CLAIM)

    binding = FinalStateBinding(
        repository_id=facts.repository_id,
        execution_run_id=facts.execution_run_id,
        pre_execution_state_fingerprint=facts.pre_execution_state_fingerprint,
        post_execution_state_fingerprint=facts.post_execution_state_fingerprint,
        final_state_fingerprint=facts.final_state_fingerprint,
        post_validation_state_fingerprint=facts.post_validation_state_fingerprint,
        validation_coverage_complete=coverage_complete,
        validated_state_current=validated_state_current,
    )

    unresolved: set[str] = {
        UNRESOLVED_SEMANTIC_GOAL_REVIEW,
        UNRESOLVED_HUMAN_REVIEW,
    }
    if preservation_unresolved:
        unresolved.add(UNRESOLVED_SEMANTIC_PRESERVATION)
    if not coverage_complete:
        unresolved.add(UNRESOLVED_VALIDATION_COVERAGE)
    if stale_present or INCONSISTENT_POST_VALIDATION_MUTATION in inconsistencies:
        unresolved.add(UNRESOLVED_VALIDATION_FRESHNESS)
    if undeclared_present or unobserved_present or mismatch_present:
        unresolved.add(UNRESOLVED_WORKER_REPORT_CORRECTION)
    if blocked_present:
        unresolved.add(UNRESOLVED_SCOPE_AUTHORIZATION)
    if not authorization.declares_worker_ownership:
        unresolved.add(UNRESOLVED_WORKER_SCOPE_OWNERSHIP)
    if not validated_state_current:
        unresolved.add(UNRESOLVED_FINAL_STATE_BINDING)

    warnings_present = bool(
        preservation_unresolved
        or any(
            item.coverage
            in {COVERAGE_OPTIONAL_MISSING, COVERAGE_ADDITIONAL_OBSERVED}
            for item in validation_findings
        )
        or INCONSISTENT_POST_VALIDATION_MUTATION in inconsistencies
    )

    if blocked_present:
        status = STATUS_BLOCKED
    elif not coverage_complete:
        status = STATUS_INCOMPLETE
    elif suspicious_present or unverified_claim or not worker_status_consistent:
        status = STATUS_SUSPICIOUS
    elif warnings_present:
        status = STATUS_RECONCILED_WITH_WARNINGS
    else:
        status = STATUS_RECONCILED

    return PostRunReconciliation(
        status=status,
        task_contract_fingerprint=authorization.task_contract_fingerprint,
        execution_authorization_fingerprint=authorization_fingerprint,
        worker_report_fingerprint=report_fingerprint,
        observed_facts_fingerprint=facts_fingerprint,
        request_fingerprint=request_fingerprint,
        declared_change_summary=declared_summary,
        observed_change_summary=observed_summary,
        change_findings=change_findings,
        validation_findings=validation_findings,
        preservation_findings=preservation_findings,
        worker_status_claim=report.declared_status,
        worker_status_consistent=worker_status_consistent,
        final_state_binding=binding,
        unresolved_requirements=_ordered_codes(
            unresolved, RECONCILIATION_UNRESOLVED_REQUIREMENTS
        ),
        reasons=_ordered_codes(reasons, RECONCILIATION_REASONS),
        inconsistencies=_ordered_codes(
            inconsistencies, RECONCILIATION_INCONSISTENCIES
        ),
        facts_collected_externally=facts.facts_collected_externally,
    )


def render_post_run_reconciliation_json(result: PostRunReconciliation) -> str:
    """Render one reconciliation as deterministic JSON."""
    if type(result) is not PostRunReconciliation:
        raise TypeError(
            "render_post_run_reconciliation_json requires an exact "
            "PostRunReconciliation"
        )
    return json.dumps(
        result.as_dict(), indent=2, ensure_ascii=False, sort_keys=False
    )


__all__ = [
    "PHASE_ID",
    "AUTHORIZATION_SCHEMA_VERSION",
    "WORKER_REPORT_SCHEMA_VERSION",
    "OBSERVED_FACTS_SCHEMA_VERSION",
    "REQUEST_SCHEMA_VERSION",
    "RESULT_SCHEMA_VERSION",
    "CHANGE_KINDS",
    "AUTHORIZED_PATH_AUTHORITIES",
    "PATH_AUTHORITIES",
    "FORBIDDEN_REASONS",
    "CHANGE_CLASSIFICATIONS",
    "SEVERITIES",
    "WORKER_STATUS_CLAIMS",
    "VALIDATION_KINDS",
    "RECEIPT_RESULTS",
    "DECLARED_VALIDATION_RESULTS",
    "VALIDATION_COVERAGE_STATES",
    "PRESERVATION_OBLIGATION_KINDS",
    "PRESERVATION_OBLIGATION_STATES",
    "RECONCILIATION_STATUSES",
    "RECONCILIATION_REASONS",
    "RECONCILIATION_INCONSISTENCIES",
    "RECONCILIATION_UNRESOLVED_REQUIREMENTS",
    "CHANGE_FINDING_REASONS",
    "VALIDATION_FINDING_REASONS",
    "RECONCILED_MEANING",
    "AuthorizedPath",
    "PathExpansionReceipt",
    "ValidationExpectation",
    "PreservationObligation",
    "ExecutionAuthorization",
    "DeclaredChange",
    "DeclaredValidationAction",
    "WorkerReport",
    "ObservedChange",
    "ValidationReceipt",
    "ObservedPostRunFacts",
    "PostRunReconciliationRequest",
    "ChangeSummary",
    "ChangeFinding",
    "ValidationFinding",
    "PreservationFinding",
    "FinalStateBinding",
    "PostRunReconciliation",
    "execution_authorization_fingerprint",
    "worker_report_fingerprint",
    "observed_post_run_facts_fingerprint",
    "validation_receipt_fingerprint",
    "reconciliation_request_fingerprint",
    "reconciliation_authority",
    "reconciliation_guardrails",
    "reconcile_post_run",
    "render_post_run_reconciliation_json",
]
