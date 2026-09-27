"""Focused CHECK.1 post-run contract reconciliation regressions.

Every fact in these tests is constructed directly: no repository is traversed,
no validation is executed, no patch is applied and no model is called.  The
static authority boundary lives in ``test_post_run_reconciliation_boundaries``.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from core.post_run_reconciliation import (
    CHANGE_ADDED,
    CHANGE_DELETED,
    CHANGE_MODIFIED,
    CHANGE_RENAMED,
    CLASSIFICATION_DECLARED_UNOBSERVED,
    CLASSIFICATION_IDENTITY_MISMATCH,
    CLASSIFICATION_KIND_MISMATCH,
    CLASSIFICATION_MATCHED,
    CLASSIFICATION_UNDECLARED,
    COVERAGE_ADDITIONAL_OBSERVED,
    COVERAGE_FAILED,
    COVERAGE_MISSING,
    COVERAGE_OPTIONAL_MISSING,
    COVERAGE_RECEIPT_INVALID,
    COVERAGE_SATISFIED,
    COVERAGE_SCOPE_MISMATCH,
    COVERAGE_STALE,
    DECLARED_VALIDATION_PASSED,
    FINDING_FORBIDDEN_PATH,
    FINDING_OUTSIDE_AUTHORIZED_SCOPE,
    FINDING_PATH_EXPANSION_APPLIED,
    FINDING_SUPPORTING_READ_ONLY,
    FINDING_VALIDATION_EXECUTE_ONLY,
    FINDING_WORKER_SCOPE,
    FORBIDDEN_SENSITIVE,
    INCONSISTENT_AUTHORIZATION_FINGERPRINT,
    INCONSISTENT_CHANGE_CLAIM_WITHOUT_CHANGES,
    INCONSISTENT_DECLARED_IDENTITY,
    INCONSISTENT_DECLARED_KIND,
    INCONSISTENT_DECLARED_UNOBSERVED,
    INCONSISTENT_FORBIDDEN_CHANGE,
    INCONSISTENT_NO_CHANGE_CLAIM,
    INCONSISTENT_OBSERVED_FACTS_FINGERPRINT,
    INCONSISTENT_OUT_OF_SCOPE_CHANGE,
    INCONSISTENT_POST_VALIDATION_MUTATION,
    INCONSISTENT_SUPPORTING_FILE_WRITTEN,
    INCONSISTENT_UNDECLARED_CHANGE,
    INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM,
    INCONSISTENT_VALIDATION_FAILED,
    INCONSISTENT_VALIDATION_FILE_WRITTEN,
    INCONSISTENT_VALIDATION_MISSING,
    INCONSISTENT_VALIDATION_RECEIPT_FINGERPRINT,
    INCONSISTENT_VALIDATION_SCOPE,
    INCONSISTENT_VALIDATION_STALE,
    INCONSISTENT_WORKER_REPORT_FINGERPRINT,
    INCONSISTENT_WORKER_SCOPE,
    INCONSISTENT_WORKER_STATUS_CLAIM,
    INCONSISTENT_WORKER_SUCCESS_CLAIM,
    OBLIGATION_BEHAVIOR_PRESERVATION,
    OBLIGATION_CERTIFICATION_UNSATISFIED,
    OBLIGATION_CERTIFIED,
    OBLIGATION_UNRESOLVED,
    PATH_AUTHORITY_FORBIDDEN,
    PATH_AUTHORITY_SUPPORTING_READ_ONLY,
    PATH_AUTHORITY_UNAUTHORIZED,
    PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY,
    PATH_AUTHORITY_WRITABLE,
    PATH_AUTHORITY_WRITABLE_WITH_REVIEW,
    RECEIPT_FAILED,
    RECEIPT_PASSED,
    RECEIPT_SKIPPED,
    RECONCILED_MEANING,
    SEVERITY_BLOCKED,
    SEVERITY_INFORMATIONAL,
    SEVERITY_SUSPICIOUS,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_INCONSISTENT_INPUT,
    STATUS_RECONCILED,
    STATUS_RECONCILED_WITH_WARNINGS,
    STATUS_SUSPICIOUS,
    UNRESOLVED_HUMAN_REVIEW,
    UNRESOLVED_SEMANTIC_GOAL_REVIEW,
    UNRESOLVED_SEMANTIC_PRESERVATION,
    UNRESOLVED_VALIDATION_COVERAGE,
    UNRESOLVED_VALIDATION_FRESHNESS,
    UNRESOLVED_WORKER_REPORT_CORRECTION,
    UNRESOLVED_WORKER_SCOPE_OWNERSHIP,
    VALIDATION_REASON_ADDITIONAL,
    VALIDATION_REASON_OPTIONAL,
    VALIDATION_REASON_SKIPPED,
    VALIDATION_REASON_STALE,
    VALIDATION_REASON_UNVERIFIED_CLAIM,
    VALIDATION_STATIC_CHECK,
    VALIDATION_TARGETED_REGRESSION,
    VALIDATION_UNIT_TESTS,
    WORKER_CLAIM_BLOCKED,
    WORKER_CLAIM_FAILED,
    WORKER_CLAIM_PARTIAL,
    WORKER_CLAIM_SUCCESS,
    AuthorizedPath,
    DeclaredChange,
    DeclaredValidationAction,
    ExecutionAuthorization,
    ObservedChange,
    ObservedPostRunFacts,
    PathExpansionReceipt,
    PostRunReconciliationRequest,
    PreservationObligation,
    ValidationExpectation,
    ValidationReceipt,
    execution_authorization_fingerprint,
    observed_post_run_facts_fingerprint,
    reconcile_post_run,
    reconciliation_authority,
    reconciliation_guardrails,
    render_post_run_reconciliation_json,
    validation_receipt_fingerprint,
    worker_report_fingerprint,
    WorkerReport,
)


# ── Fixture helpers ───────────────────────────────────────────────────────────

RUN = "RUN-1"
REPO = "REPO-1"
TASK = "TASK-CONTRACT-A"

ROUTER = "core/router.py"
SESSION = "core/session.py"
CONFIG = "core/config.py"
NOTES = "docs/notes.md"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


S0 = digest("state-0")
S1 = digest("state-1")
S2 = digest("state-2")


def authorization(
    *,
    authorized_paths: tuple[AuthorizedPath, ...] | None = None,
    validation_expectations: tuple[ValidationExpectation, ...] | None = None,
    preservation_obligations: tuple[PreservationObligation, ...] = (),
    path_expansion_receipts: tuple[PathExpansionReceipt, ...] = (),
    task_label: str = TASK,
    worker_id: str | None = None,
) -> ExecutionAuthorization:
    return ExecutionAuthorization(
        authorization_id="AUTH-1",
        execution_run_id=RUN,
        repository_id=REPO,
        task_contract_fingerprint=digest(task_label),
        pre_execution_state_fingerprint=S0,
        authorized_paths=(
            (AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),)
            if authorized_paths is None
            else authorized_paths
        ),
        validation_expectations=(
            (
                ValidationExpectation(
                    validation_id="V-unit",
                    validation_kind=VALIDATION_UNIT_TESTS,
                    required=True,
                    target_scope=("tests/test_router.py",),
                ),
            )
            if validation_expectations is None
            else validation_expectations
        ),
        preservation_obligations=preservation_obligations,
        path_expansion_receipts=path_expansion_receipts,
        worker_id=worker_id,
    )


def report(
    *,
    declared_status: str = WORKER_CLAIM_SUCCESS,
    declared_changes: tuple[DeclaredChange, ...] | None = None,
    declared_validation_actions: tuple[DeclaredValidationAction, ...] | None = None,
    declared_limitations: tuple[str, ...] = (),
    declared_unresolved_items: tuple[str, ...] = (),
    worker_id: str | None = None,
) -> WorkerReport:
    return WorkerReport(
        report_id="REPORT-1",
        execution_run_id=RUN,
        declared_status=declared_status,
        declared_changes=(
            (DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),)
            if declared_changes is None
            else declared_changes
        ),
        declared_validation_actions=(
            (
                DeclaredValidationAction(
                    validation_id="V-unit",
                    validation_kind=VALIDATION_UNIT_TESTS,
                    declared_result=DECLARED_VALIDATION_PASSED,
                ),
            )
            if declared_validation_actions is None
            else declared_validation_actions
        ),
        declared_limitations=declared_limitations,
        declared_unresolved_items=declared_unresolved_items,
        worker_id=worker_id,
    )


def receipt(
    *,
    receipt_id: str = "RECEIPT-1",
    validation_id: str = "V-unit",
    validation_kind: str = VALIDATION_UNIT_TESTS,
    result: str = RECEIPT_PASSED,
    state_fingerprint: str = S1,
    target_scope: tuple[str, ...] = ("tests/test_router.py",),
    execution_run_id: str = RUN,
    repository_id: str = REPO,
) -> ValidationReceipt:
    return ValidationReceipt(
        receipt_id=receipt_id,
        validation_id=validation_id,
        execution_run_id=execution_run_id,
        repository_id=repository_id,
        validation_kind=validation_kind,
        result=result,
        state_fingerprint=state_fingerprint,
        target_scope=target_scope,
    )


def facts(
    *,
    observed_changes: tuple[ObservedChange, ...] | None = None,
    validation_receipts: tuple[ValidationReceipt, ...] | None = None,
    post_execution_state_fingerprint: str = S1,
    final_state_fingerprint: str = S1,
    post_validation_state_fingerprint: str | None = None,
    rename_detection_supported: bool = False,
) -> ObservedPostRunFacts:
    return ObservedPostRunFacts(
        facts_id="FACTS-1",
        execution_run_id=RUN,
        repository_id=REPO,
        pre_execution_state_fingerprint=S0,
        post_execution_state_fingerprint=post_execution_state_fingerprint,
        final_state_fingerprint=final_state_fingerprint,
        observed_changes=(
            (
                ObservedChange(
                    path=ROUTER,
                    change_kind=CHANGE_MODIFIED,
                    before_sha256=digest("router-0"),
                    after_sha256=digest("router-1"),
                ),
            )
            if observed_changes is None
            else observed_changes
        ),
        validation_receipts=(
            (receipt(),) if validation_receipts is None else validation_receipts
        ),
        post_validation_state_fingerprint=post_validation_state_fingerprint,
        rename_detection_supported=rename_detection_supported,
    )


def request(
    auth: ExecutionAuthorization,
    worker: WorkerReport,
    observed: ObservedPostRunFacts,
    *,
    bind_receipts: bool = False,
    **overrides: str,
) -> PostRunReconciliationRequest:
    payload = {
        "expected_task_contract_fingerprint": auth.task_contract_fingerprint,
        "expected_authorization_fingerprint": execution_authorization_fingerprint(
            auth
        ),
        "expected_worker_report_fingerprint": worker_report_fingerprint(worker),
        "expected_observed_facts_fingerprint": observed_post_run_facts_fingerprint(
            observed
        ),
    }
    payload.update(overrides)
    receipts = ()
    if bind_receipts:
        receipts = tuple(
            sorted(
                validation_receipt_fingerprint(item)
                for item in observed.validation_receipts
            )
        )
    return PostRunReconciliationRequest(
        authorization=auth,
        worker_report=worker,
        observed_facts=observed,
        expected_validation_receipt_fingerprints=receipts,
        **payload,
    )


def reconcile(
    auth: ExecutionAuthorization,
    worker: WorkerReport,
    observed: ObservedPostRunFacts,
    **kwargs,
):
    return reconcile_post_run(request(auth, worker, observed, **kwargs))


def finding_for(result, path: str):
    matches = [item for item in result.change_findings if item.path == path]
    assert matches, f"no change finding for {path}"
    return matches[0]


def validation_for(result, validation_id: str):
    matches = [
        item for item in result.validation_findings if item.validation_id == validation_id
    ]
    assert matches, f"no validation finding for {validation_id}"
    return matches[0]


# ── The clean baseline ────────────────────────────────────────────────────────

def test_clean_run_reconciles():
    result = reconcile(authorization(), report(), facts())

    assert result.status == STATUS_RECONCILED
    assert result.inconsistencies == ()
    assert result.worker_status_consistent is True
    assert finding_for(result, ROUTER).classification == CLASSIFICATION_MATCHED
    assert finding_for(result, ROUTER).severity == SEVERITY_INFORMATIONAL
    assert validation_for(result, "V-unit").coverage == COVERAGE_SATISFIED
    assert result.final_state_binding.validation_coverage_complete is True
    assert result.final_state_binding.validated_state_current is True


def test_even_a_reconciled_result_leaves_semantic_review_outstanding():
    result = reconcile(authorization(), report(), facts())

    assert result.status == STATUS_RECONCILED
    assert UNRESOLVED_SEMANTIC_GOAL_REVIEW in result.unresolved_requirements
    assert UNRESOLVED_HUMAN_REVIEW in result.unresolved_requirements
    assert result.check_2_required is True
    assert result.semantic_goal_review_authority is False
    assert result.implementation_correctness_authority is False
    assert result.final_success_authority is False


# ── §46 note vs diff ──────────────────────────────────────────────────────────

def test_a_declared_change_that_was_observed_is_matched():
    result = reconcile(authorization(), report(), facts())

    assert [item.path for item in result.matched_changes] == [ROUTER]
    assert result.undeclared_changes == ()
    assert result.declared_but_unobserved_changes == ()


def test_b_undeclared_but_allowed_change_is_suspicious_and_visible():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(path=SESSION, authority=PATH_AUTHORITY_WRITABLE),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=SESSION,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("session-0"),
                after_sha256=digest("session-1"),
            ),
        )
    )
    result = reconcile(auth, report(), observed)

    finding = finding_for(result, SESSION)
    assert finding.classification == CLASSIFICATION_UNDECLARED
    assert finding.severity == SEVERITY_SUSPICIOUS
    assert finding.path_authority == PATH_AUTHORITY_WRITABLE
    assert INCONSISTENT_UNDECLARED_CHANGE in result.inconsistencies
    assert result.status == STATUS_SUSPICIOUS
    assert UNRESOLVED_WORKER_REPORT_CORRECTION in result.unresolved_requirements


def test_c_undeclared_forbidden_change_is_blocked():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(
                path=CONFIG,
                authority=PATH_AUTHORITY_FORBIDDEN,
                forbidden_reason=FORBIDDEN_SENSITIVE,
            ),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=CONFIG,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("config-0"),
                after_sha256=digest("config-1"),
            ),
        )
    )
    result = reconcile(auth, report(), observed)

    finding = finding_for(result, CONFIG)
    assert finding.classification == CLASSIFICATION_UNDECLARED
    assert finding.severity == SEVERITY_BLOCKED
    assert finding.forbidden_reason == FORBIDDEN_SENSITIVE
    assert FINDING_FORBIDDEN_PATH in finding.reason_codes
    assert INCONSISTENT_FORBIDDEN_CHANGE in result.inconsistencies
    assert result.status == STATUS_BLOCKED


def test_d_declared_but_unobserved_change_is_recorded_not_fabricated():
    worker = report(
        declared_changes=(
            DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
            DeclaredChange(path=SESSION, change_kind=CHANGE_MODIFIED),
        )
    )
    result = reconcile(authorization(), worker, facts())

    finding = finding_for(result, SESSION)
    assert finding.classification == CLASSIFICATION_DECLARED_UNOBSERVED
    assert finding.severity == SEVERITY_SUSPICIOUS
    assert finding.observed_change_kind is None
    assert INCONSISTENT_DECLARED_UNOBSERVED in result.inconsistencies
    assert result.status == STATUS_SUSPICIOUS
    # The observed summary never gains the fabricated path.
    assert SESSION not in result.observed_change_summary.modified_paths
    assert SESSION in result.declared_change_summary.modified_paths


def test_e_declaring_no_change_while_changes_were_observed_is_a_serious_mismatch():
    worker = report(declared_changes=())
    result = reconcile(authorization(), worker, facts())

    assert INCONSISTENT_NO_CHANGE_CLAIM in result.inconsistencies
    assert INCONSISTENT_UNDECLARED_CHANGE in result.inconsistencies
    assert finding_for(result, ROUTER).classification == CLASSIFICATION_UNDECLARED
    assert result.status == STATUS_SUSPICIOUS
    assert result.worker_status_consistent is False


def test_f_declaring_a_change_while_none_was_observed_is_an_overclaim():
    observed = facts(
        observed_changes=(),
        post_execution_state_fingerprint=S0,
        final_state_fingerprint=S0,
        validation_receipts=(receipt(state_fingerprint=S0),),
    )
    result = reconcile(authorization(), report(), observed)

    assert INCONSISTENT_CHANGE_CLAIM_WITHOUT_CHANGES in result.inconsistencies
    assert INCONSISTENT_DECLARED_UNOBSERVED in result.inconsistencies
    assert finding_for(result, ROUTER).classification == (
        CLASSIFICATION_DECLARED_UNOBSERVED
    )
    assert result.status == STATUS_SUSPICIOUS


def test_worker_report_omission_stays_visible_even_for_an_allowed_file():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(path=NOTES, authority=PATH_AUTHORITY_WRITABLE),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=NOTES, change_kind=CHANGE_ADDED, after_sha256=digest("notes-1")
            ),
        )
    )
    result = reconcile(auth, report(), observed)

    assert NOTES in [item.path for item in result.undeclared_changes]
    assert NOTES not in result.declared_change_summary.added_paths
    assert NOTES in result.observed_change_summary.added_paths


def test_declared_change_kind_mismatch_is_surfaced():
    worker = report(
        declared_changes=(DeclaredChange(path=ROUTER, change_kind=CHANGE_ADDED),)
    )
    result = reconcile(authorization(), worker, facts())

    finding = finding_for(result, ROUTER)
    assert finding.classification == CLASSIFICATION_KIND_MISMATCH
    assert finding.declared_change_kind == CHANGE_ADDED
    assert finding.observed_change_kind == CHANGE_MODIFIED
    assert INCONSISTENT_DECLARED_KIND in result.inconsistencies
    assert result.status == STATUS_SUSPICIOUS


def test_declared_change_bound_to_a_different_revision_is_surfaced():
    other = ObservedChange(
        path=ROUTER,
        change_kind=CHANGE_MODIFIED,
        before_sha256=digest("router-0"),
        after_sha256=digest("router-OTHER"),
    )
    worker = report(
        declared_changes=(
            DeclaredChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                expected_change_identity_sha256=other.change_identity_sha256,
            ),
        )
    )
    result = reconcile(authorization(), worker, facts())

    finding = finding_for(result, ROUTER)
    assert finding.classification == CLASSIFICATION_IDENTITY_MISMATCH
    assert INCONSISTENT_DECLARED_IDENTITY in result.inconsistencies
    assert result.status == STATUS_SUSPICIOUS


# ── §47 authorized scope ──────────────────────────────────────────────────────

def test_g_change_inside_the_authorized_set_is_reconciled():
    result = reconcile(authorization(), report(), facts())

    assert result.status == STATUS_RECONCILED
    assert result.out_of_scope_changes == ()
    assert result.forbidden_changes == ()


def test_h_change_outside_the_authorized_set_is_blocked():
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=SESSION,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("session-0"),
                after_sha256=digest("session-1"),
            ),
        )
    )
    result = reconcile(authorization(), report(), observed)

    finding = finding_for(result, SESSION)
    assert finding.path_authority == PATH_AUTHORITY_UNAUTHORIZED
    assert FINDING_OUTSIDE_AUTHORIZED_SCOPE in finding.reason_codes
    assert finding.severity == SEVERITY_BLOCKED
    assert INCONSISTENT_OUT_OF_SCOPE_CHANGE in result.inconsistencies
    assert result.status == STATUS_BLOCKED
    assert SESSION in [item.path for item in result.out_of_scope_changes]


def test_i_a_declared_forbidden_change_is_still_blocked():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(
                path=CONFIG,
                authority=PATH_AUTHORITY_FORBIDDEN,
                forbidden_reason=FORBIDDEN_SENSITIVE,
            ),
        )
    )
    worker = report(
        declared_changes=(
            DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
            DeclaredChange(path=CONFIG, change_kind=CHANGE_MODIFIED),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=CONFIG,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("config-0"),
                after_sha256=digest("config-1"),
            ),
        )
    )
    result = reconcile(auth, worker, observed)

    finding = finding_for(result, CONFIG)
    assert finding.classification == CLASSIFICATION_MATCHED
    assert finding.severity == SEVERITY_BLOCKED
    assert INCONSISTENT_FORBIDDEN_CHANGE in result.inconsistencies
    assert result.status == STATUS_BLOCKED


def test_j_writing_a_supporting_read_only_file_is_blocked():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(
                path=SESSION, authority=PATH_AUTHORITY_SUPPORTING_READ_ONLY
            ),
        )
    )
    worker = report(
        declared_changes=(
            DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
            DeclaredChange(path=SESSION, change_kind=CHANGE_MODIFIED),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=SESSION,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("session-0"),
                after_sha256=digest("session-1"),
            ),
        )
    )
    result = reconcile(auth, worker, observed)

    finding = finding_for(result, SESSION)
    assert FINDING_SUPPORTING_READ_ONLY in finding.reason_codes
    assert finding.severity == SEVERITY_BLOCKED
    assert INCONSISTENT_SUPPORTING_FILE_WRITTEN in result.inconsistencies
    assert result.status == STATUS_BLOCKED


def test_k_writing_a_validation_only_file_is_blocked():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(
                path="tests/test_router.py",
                authority=PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY,
            ),
        )
    )
    worker = report(
        declared_changes=(
            DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
            DeclaredChange(path="tests/test_router.py", change_kind=CHANGE_MODIFIED),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path="tests/test_router.py",
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("test-0"),
                after_sha256=digest("test-1"),
            ),
        )
    )
    result = reconcile(auth, worker, observed)

    finding = finding_for(result, "tests/test_router.py")
    assert FINDING_VALIDATION_EXECUTE_ONLY in finding.reason_codes
    assert finding.severity == SEVERITY_BLOCKED
    assert INCONSISTENT_VALIDATION_FILE_WRITTEN in result.inconsistencies
    assert result.status == STATUS_BLOCKED


def test_read_authority_is_never_write_authority():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(
                path=SESSION, authority=PATH_AUTHORITY_SUPPORTING_READ_ONLY
            ),
        )
    )
    entry = auth.authorized_paths[0]
    assert entry.write_authorized is False


def test_an_explicit_expansion_receipt_widens_the_authorized_set():
    auth = authorization(
        path_expansion_receipts=(
            PathExpansionReceipt(
                path=SESSION,
                authority=PATH_AUTHORITY_WRITABLE_WITH_REVIEW,
                approval_receipt_sha256=digest("approval"),
            ),
        )
    )
    worker = report(
        declared_changes=(
            DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
            DeclaredChange(path=SESSION, change_kind=CHANGE_MODIFIED),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=SESSION,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("session-0"),
                after_sha256=digest("session-1"),
            ),
        )
    )
    result = reconcile(auth, worker, observed)

    finding = finding_for(result, SESSION)
    assert finding.path_authority == PATH_AUTHORITY_WRITABLE_WITH_REVIEW
    assert FINDING_PATH_EXPANSION_APPLIED in finding.reason_codes
    assert result.status == STATUS_RECONCILED


def test_an_expansion_receipt_can_never_reach_a_forbidden_path():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(
                path=CONFIG,
                authority=PATH_AUTHORITY_FORBIDDEN,
                forbidden_reason=FORBIDDEN_SENSITIVE,
            ),
        ),
        path_expansion_receipts=(
            PathExpansionReceipt(
                path=CONFIG,
                authority=PATH_AUTHORITY_WRITABLE,
                approval_receipt_sha256=digest("approval"),
            ),
        ),
    )
    result = reconcile(auth, report(), facts())
    assert result.status == STATUS_INCONSISTENT_INPUT


# ── §40 worker ownership ──────────────────────────────────────────────────────

def test_a_worker_writing_another_workers_file_is_out_of_worker_scope():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(
                path=ROUTER, authority=PATH_AUTHORITY_WRITABLE, worker_id="worker-a"
            ),
            AuthorizedPath(
                path=SESSION, authority=PATH_AUTHORITY_WRITABLE, worker_id="worker-b"
            ),
        )
    )
    worker = report(
        worker_id="worker-a",
        declared_changes=(
            DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
            DeclaredChange(path=SESSION, change_kind=CHANGE_MODIFIED),
        ),
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=SESSION,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("session-0"),
                after_sha256=digest("session-1"),
            ),
        )
    )
    result = reconcile(auth, worker, observed)

    finding = finding_for(result, SESSION)
    assert FINDING_WORKER_SCOPE in finding.reason_codes
    assert finding.severity == SEVERITY_BLOCKED
    assert INCONSISTENT_WORKER_SCOPE in result.inconsistencies
    assert result.status == STATUS_BLOCKED
    assert UNRESOLVED_WORKER_SCOPE_OWNERSHIP not in result.unresolved_requirements


def test_absent_worker_ownership_is_a_declared_limitation_not_an_invention():
    result = reconcile(authorization(), report(), facts())

    assert authorization().declares_worker_ownership is False
    assert UNRESOLVED_WORKER_SCOPE_OWNERSHIP in result.unresolved_requirements
    assert INCONSISTENT_WORKER_SCOPE not in result.inconsistencies


# ── §48 validation ────────────────────────────────────────────────────────────

def test_l_fresh_passing_required_validation_reconciles():
    result = reconcile(authorization(), report(), facts())

    finding = validation_for(result, "V-unit")
    assert finding.coverage == COVERAGE_SATISFIED
    assert finding.receipt_result == RECEIPT_PASSED
    assert finding.receipt_state_fingerprint == S1
    assert result.status == STATUS_RECONCILED


def test_m_missing_required_validation_is_incomplete():
    result = reconcile(authorization(), report(), facts(validation_receipts=()))

    finding = validation_for(result, "V-unit")
    assert finding.coverage == COVERAGE_MISSING
    assert INCONSISTENT_VALIDATION_MISSING in result.inconsistencies
    assert result.status == STATUS_INCOMPLETE
    assert UNRESOLVED_VALIDATION_COVERAGE in result.unresolved_requirements


def test_n_failed_required_validation_is_blocked_and_never_reconciled():
    observed = facts(validation_receipts=(receipt(result=RECEIPT_FAILED),))
    result = reconcile(authorization(), report(), observed)

    assert validation_for(result, "V-unit").coverage == COVERAGE_FAILED
    assert INCONSISTENT_VALIDATION_FAILED in result.inconsistencies
    assert result.status == STATUS_BLOCKED
    assert result.status not in {STATUS_RECONCILED, STATUS_RECONCILED_WITH_WARNINGS}


def test_o_worker_prose_style_claim_without_a_receipt_is_unverified():
    result = reconcile(authorization(), report(), facts(validation_receipts=()))

    finding = validation_for(result, "V-unit")
    assert VALIDATION_REASON_UNVERIFIED_CLAIM in finding.reason_codes
    assert INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM in result.inconsistencies
    assert result.status == STATUS_INCOMPLETE


def test_o_unverified_claim_alone_is_suspicious_when_nothing_was_required():
    auth = authorization(validation_expectations=())
    worker = report(
        declared_validation_actions=(
            DeclaredValidationAction(
                validation_kind=VALIDATION_UNIT_TESTS,
                declared_result=DECLARED_VALIDATION_PASSED,
            ),
        )
    )
    result = reconcile(auth, worker, facts(validation_receipts=()))

    assert INCONSISTENT_UNVERIFIED_VALIDATION_CLAIM in result.inconsistencies
    assert result.status == STATUS_SUSPICIOUS


def test_p_a_receipt_for_a_different_scope_does_not_satisfy_the_expectation():
    auth = authorization(
        validation_expectations=(
            ValidationExpectation(
                validation_id="V-unit",
                validation_kind=VALIDATION_UNIT_TESTS,
                required=True,
                target_scope=("tests/test_indexer.py",),
            ),
        )
    )
    observed = facts(
        validation_receipts=(receipt(target_scope=("tests/test_parser.py",)),)
    )
    result = reconcile(auth, report(), observed)

    assert validation_for(result, "V-unit").coverage == COVERAGE_SCOPE_MISMATCH
    assert INCONSISTENT_VALIDATION_SCOPE in result.inconsistencies
    assert result.status == STATUS_INCOMPLETE


def test_q_a_missing_optional_validation_warns_without_blocking():
    auth = authorization(
        validation_expectations=(
            ValidationExpectation(
                validation_id="V-unit",
                validation_kind=VALIDATION_UNIT_TESTS,
                required=True,
                target_scope=("tests/test_router.py",),
            ),
            ValidationExpectation(
                validation_id="V-lint",
                validation_kind=VALIDATION_STATIC_CHECK,
                required=False,
            ),
        )
    )
    result = reconcile(auth, report(), facts())

    finding = validation_for(result, "V-lint")
    assert finding.coverage == COVERAGE_OPTIONAL_MISSING
    assert VALIDATION_REASON_OPTIONAL in finding.reason_codes
    assert result.status == STATUS_RECONCILED_WITH_WARNINGS
    assert UNRESOLVED_VALIDATION_COVERAGE not in result.unresolved_requirements


def test_partial_validation_coverage_is_incomplete_even_when_the_run_tests_pass():
    auth = authorization(
        validation_expectations=(
            ValidationExpectation(
                validation_id="V-unit",
                validation_kind=VALIDATION_UNIT_TESTS,
                required=True,
                target_scope=("tests/test_router.py",),
            ),
            ValidationExpectation(
                validation_id="V-static",
                validation_kind=VALIDATION_STATIC_CHECK,
                required=True,
            ),
            ValidationExpectation(
                validation_id="V-regression",
                validation_kind=VALIDATION_TARGETED_REGRESSION,
                required=True,
            ),
        )
    )
    result = reconcile(auth, report(), facts())

    assert validation_for(result, "V-unit").coverage == COVERAGE_SATISFIED
    assert validation_for(result, "V-static").coverage == COVERAGE_MISSING
    assert validation_for(result, "V-regression").coverage == COVERAGE_MISSING
    assert result.status == STATUS_INCOMPLETE


def test_an_extra_validation_cannot_discharge_a_missing_required_one():
    auth = authorization(
        validation_expectations=(
            ValidationExpectation(
                validation_id="V-static",
                validation_kind=VALIDATION_STATIC_CHECK,
                required=True,
            ),
        )
    )
    worker = report(declared_validation_actions=())
    result = reconcile(auth, worker, facts())

    assert validation_for(result, "V-static").coverage == COVERAGE_MISSING
    extra = [
        item
        for item in result.additional_validation_observed
        if item.validation_id == "V-unit"
    ]
    assert extra and extra[0].coverage == COVERAGE_ADDITIONAL_OBSERVED
    assert VALIDATION_REASON_ADDITIONAL in extra[0].reason_codes
    assert result.status == STATUS_INCOMPLETE


def test_a_skipped_receipt_is_not_an_execution():
    observed = facts(validation_receipts=(receipt(result=RECEIPT_SKIPPED),))
    result = reconcile(authorization(), report(), observed)

    finding = validation_for(result, "V-unit")
    assert finding.coverage == COVERAGE_MISSING
    assert VALIDATION_REASON_SKIPPED in finding.reason_codes
    assert result.status == STATUS_INCOMPLETE


def test_a_receipt_from_another_run_or_repository_is_invalid():
    observed = facts(validation_receipts=(receipt(execution_run_id=RUN),))
    other = facts(
        validation_receipts=(
            receipt(validation_kind=VALIDATION_STATIC_CHECK),
        )
    )
    assert reconcile(authorization(), report(), observed).status == STATUS_RECONCILED
    result = reconcile(authorization(), report(), other)
    assert validation_for(result, "V-unit").coverage == COVERAGE_RECEIPT_INVALID
    assert result.status == STATUS_INCOMPLETE


def test_an_expectation_state_binding_must_match_the_receipt():
    auth = authorization(
        validation_expectations=(
            ValidationExpectation(
                validation_id="V-unit",
                validation_kind=VALIDATION_UNIT_TESTS,
                required=True,
                target_scope=("tests/test_router.py",),
                expected_state_fingerprint=S2,
            ),
        )
    )
    result = reconcile(auth, report(), facts())

    assert validation_for(result, "V-unit").coverage == COVERAGE_RECEIPT_INVALID
    assert result.status == STATUS_INCOMPLETE


# ── §49 / §50 validation freshness ────────────────────────────────────────────

def test_r_a_receipt_bound_to_an_earlier_state_is_stale_for_the_final_state():
    observed = facts(
        validation_receipts=(receipt(state_fingerprint=S1),),
        post_execution_state_fingerprint=S1,
        final_state_fingerprint=S2,
    )
    result = reconcile(authorization(), report(), observed)

    finding = validation_for(result, "V-unit")
    assert finding.coverage == COVERAGE_STALE
    assert VALIDATION_REASON_STALE in finding.reason_codes
    assert INCONSISTENT_VALIDATION_STALE in result.inconsistencies
    assert result.status == STATUS_INCOMPLETE
    assert result.final_state_binding.validated_state_current is False
    assert UNRESOLVED_VALIDATION_FRESHNESS in result.unresolved_requirements


def test_s_a_change_after_validation_makes_validation_not_current():
    """A.py validated at H1, then B.py changes: H1 no longer certifies H2."""
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(path=NOTES, authority=PATH_AUTHORITY_WRITABLE),
        )
    )
    worker = report(
        declared_changes=(
            DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
            DeclaredChange(path=NOTES, change_kind=CHANGE_ADDED),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=NOTES, change_kind=CHANGE_ADDED, after_sha256=digest("notes-1")
            ),
        ),
        validation_receipts=(receipt(state_fingerprint=S1),),
        post_execution_state_fingerprint=S1,
        final_state_fingerprint=S2,
    )
    result = reconcile(auth, worker, observed)

    # Every change is declared and authorized, yet the run is not certified.
    assert result.undeclared_changes == ()
    assert result.forbidden_changes == ()
    assert validation_for(result, "V-unit").coverage == COVERAGE_STALE
    assert result.status == STATUS_INCOMPLETE
    assert result.worker_status_consistent is False


def test_a_state_mutation_after_validation_is_recorded():
    observed = facts(
        validation_receipts=(receipt(state_fingerprint=S1),),
        post_validation_state_fingerprint=S2,
    )
    result = reconcile(authorization(), report(), observed)

    assert INCONSISTENT_POST_VALIDATION_MUTATION in result.inconsistencies
    assert UNRESOLVED_VALIDATION_FRESHNESS in result.unresolved_requirements


# ── §51 worker status claim ───────────────────────────────────────────────────

def test_t_a_success_claim_over_clean_facts_is_consistent():
    result = reconcile(authorization(), report(), facts())

    assert result.worker_status_claim == WORKER_CLAIM_SUCCESS
    assert result.worker_status_consistent is True
    assert INCONSISTENT_WORKER_SUCCESS_CLAIM not in result.inconsistencies


def test_u_a_success_claim_over_a_failed_validation_is_inconsistent():
    observed = facts(validation_receipts=(receipt(result=RECEIPT_FAILED),))
    result = reconcile(authorization(), report(), observed)

    assert result.worker_status_consistent is False
    assert INCONSISTENT_WORKER_SUCCESS_CLAIM in result.inconsistencies
    assert result.status == STATUS_BLOCKED


def test_v_a_success_claim_over_a_forbidden_change_is_inconsistent_and_blocked():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(
                path=CONFIG,
                authority=PATH_AUTHORITY_FORBIDDEN,
                forbidden_reason=FORBIDDEN_SENSITIVE,
            ),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=CONFIG,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("config-0"),
                after_sha256=digest("config-1"),
            ),
        )
    )
    result = reconcile(auth, report(), observed)

    assert result.worker_status_consistent is False
    assert INCONSISTENT_WORKER_SUCCESS_CLAIM in result.inconsistencies
    assert result.status == STATUS_BLOCKED


def test_w_a_partial_claim_over_incomplete_validation_is_consistent():
    worker = report(
        declared_status=WORKER_CLAIM_PARTIAL, declared_validation_actions=()
    )
    result = reconcile(authorization(), worker, facts(validation_receipts=()))

    assert result.worker_status_consistent is True
    assert INCONSISTENT_WORKER_STATUS_CLAIM not in result.inconsistencies
    assert result.status == STATUS_INCOMPLETE


def test_a_failed_or_blocked_claim_is_contradicted_only_by_a_scope_violation():
    for claim in (WORKER_CLAIM_FAILED, WORKER_CLAIM_BLOCKED):
        clean = reconcile(
            authorization(),
            report(declared_status=claim, declared_validation_actions=()),
            facts(validation_receipts=()),
        )
        assert clean.worker_status_consistent is True

    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(
                path=CONFIG,
                authority=PATH_AUTHORITY_FORBIDDEN,
                forbidden_reason=FORBIDDEN_SENSITIVE,
            ),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=CONFIG,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("config-0"),
                after_sha256=digest("config-1"),
            ),
        )
    )
    violation = reconcile(
        auth, report(declared_status=WORKER_CLAIM_FAILED), observed
    )
    assert violation.worker_status_consistent is False
    assert INCONSISTENT_WORKER_STATUS_CLAIM in violation.inconsistencies


# ── §52 preservation obligations ──────────────────────────────────────────────

def test_x_a_preservation_obligation_stays_unresolved_without_a_certifying_receipt():
    auth = authorization(
        preservation_obligations=(
            PreservationObligation(
                obligation_id="OBL-1",
                kind=OBLIGATION_BEHAVIOR_PRESERVATION,
                text_sha256=digest("do not change embedding behavior"),
            ),
        )
    )
    result = reconcile(auth, report(), facts())

    obligation = result.preservation_findings[0]
    assert obligation.state == OBLIGATION_UNRESOLVED
    assert UNRESOLVED_SEMANTIC_PRESERVATION in result.unresolved_requirements
    assert result.check_2_required is True
    # Every path-level check passed, yet preservation is not claimed satisfied.
    assert result.undeclared_changes == ()
    assert validation_for(result, "V-unit").coverage == COVERAGE_SATISFIED
    assert result.status == STATUS_RECONCILED_WITH_WARNINGS


def test_a_preservation_obligation_certified_by_a_bound_receipt_is_resolved():
    auth = authorization(
        validation_expectations=(
            ValidationExpectation(
                validation_id="V-invariant",
                validation_kind=VALIDATION_UNIT_TESTS,
                required=True,
                target_scope=("tests/test_embedding_invariant.py",),
            ),
        ),
        preservation_obligations=(
            PreservationObligation(
                obligation_id="OBL-1",
                kind=OBLIGATION_BEHAVIOR_PRESERVATION,
                text_sha256=digest("do not change embedding behavior"),
                certifying_validation_id="V-invariant",
            ),
        ),
    )
    worker = report(
        declared_validation_actions=(
            DeclaredValidationAction(
                validation_id="V-invariant",
                validation_kind=VALIDATION_UNIT_TESTS,
                declared_result=DECLARED_VALIDATION_PASSED,
            ),
        )
    )
    observed = facts(
        validation_receipts=(
            receipt(
                validation_id="V-invariant",
                target_scope=("tests/test_embedding_invariant.py",),
            ),
        )
    )
    result = reconcile(auth, worker, observed)

    assert result.preservation_findings[0].state == OBLIGATION_CERTIFIED
    assert UNRESOLVED_SEMANTIC_PRESERVATION not in result.unresolved_requirements
    assert result.status == STATUS_RECONCILED


def test_a_stale_certifying_receipt_does_not_certify_the_obligation():
    auth = authorization(
        preservation_obligations=(
            PreservationObligation(
                obligation_id="OBL-1",
                kind=OBLIGATION_BEHAVIOR_PRESERVATION,
                text_sha256=digest("do not change embedding behavior"),
                certifying_validation_id="V-unit",
            ),
        )
    )
    observed = facts(
        validation_receipts=(receipt(state_fingerprint=S1),),
        final_state_fingerprint=S2,
    )
    result = reconcile(auth, report(), observed)

    assert result.preservation_findings[0].state == (
        OBLIGATION_CERTIFICATION_UNSATISFIED
    )
    assert UNRESOLVED_SEMANTIC_PRESERVATION in result.unresolved_requirements


def test_53_identical_facts_under_two_task_contracts_keep_distinct_obligations():
    change_router = authorization(task_label="TASK-change-router")
    preserve_router = authorization(
        task_label="TASK-preserve-router",
        preservation_obligations=(
            PreservationObligation(
                obligation_id="OBL-router",
                kind=OBLIGATION_BEHAVIOR_PRESERVATION,
                text_sha256=digest("preserve router behavior"),
            ),
        ),
    )
    worker = report()
    observed = facts()

    a = reconcile(change_router, worker, observed)
    b = reconcile(preserve_router, worker, observed)

    assert a.observed_change_summary == b.observed_change_summary
    assert a.task_contract_fingerprint != b.task_contract_fingerprint
    assert a.preservation_findings == ()
    assert b.preservation_findings[0].obligation_id == "OBL-router"
    assert UNRESOLVED_SEMANTIC_PRESERVATION not in a.unresolved_requirements
    assert UNRESOLVED_SEMANTIC_PRESERVATION in b.unresolved_requirements
    # Neither result judges the change semantically.
    assert a.check_2_required is True
    assert b.check_2_required is True


# ── §54 tamper binding ────────────────────────────────────────────────────────

def test_y_a_worker_report_edited_after_its_fingerprint_is_invalid():
    auth = authorization()
    original = report()
    tampered = report(
        declared_changes=(DeclaredChange(path=SESSION, change_kind=CHANGE_MODIFIED),)
    )
    payload = request(auth, original, facts())
    forged = PostRunReconciliationRequest(
        authorization=auth,
        worker_report=tampered,
        observed_facts=facts(),
        expected_task_contract_fingerprint=(
            payload.expected_task_contract_fingerprint
        ),
        expected_authorization_fingerprint=(
            payload.expected_authorization_fingerprint
        ),
        expected_worker_report_fingerprint=(
            payload.expected_worker_report_fingerprint
        ),
        expected_observed_facts_fingerprint=(
            payload.expected_observed_facts_fingerprint
        ),
    )
    result = reconcile_post_run(forged)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_WORKER_REPORT_FINGERPRINT in result.inconsistencies
    assert result.post_run_reconciliation_authority is False


def test_z_observed_facts_edited_after_their_fingerprint_are_invalid():
    auth = authorization()
    worker = report()
    original = facts()
    tampered = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-TAMPERED"),
            ),
        )
    )
    forged = PostRunReconciliationRequest(
        authorization=auth,
        worker_report=worker,
        observed_facts=tampered,
        expected_task_contract_fingerprint=auth.task_contract_fingerprint,
        expected_authorization_fingerprint=execution_authorization_fingerprint(auth),
        expected_worker_report_fingerprint=worker_report_fingerprint(worker),
        expected_observed_facts_fingerprint=observed_post_run_facts_fingerprint(
            original
        ),
    )
    result = reconcile_post_run(forged)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_OBSERVED_FACTS_FINGERPRINT in result.inconsistencies


def test_aa_an_edited_authorization_is_invalid():
    original = authorization()
    widened = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(path=CONFIG, authority=PATH_AUTHORITY_WRITABLE),
        )
    )
    worker = report()
    observed = facts()
    forged = PostRunReconciliationRequest(
        authorization=widened,
        worker_report=worker,
        observed_facts=observed,
        expected_task_contract_fingerprint=original.task_contract_fingerprint,
        expected_authorization_fingerprint=execution_authorization_fingerprint(
            original
        ),
        expected_worker_report_fingerprint=worker_report_fingerprint(worker),
        expected_observed_facts_fingerprint=observed_post_run_facts_fingerprint(
            observed
        ),
    )
    result = reconcile_post_run(forged)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_AUTHORIZATION_FINGERPRINT in result.inconsistencies


def test_ab_an_edited_validation_receipt_is_invalid():
    auth = authorization()
    worker = report()
    honest = facts()
    tampered = facts(validation_receipts=(receipt(result=RECEIPT_FAILED),))
    forged = PostRunReconciliationRequest(
        authorization=auth,
        worker_report=worker,
        observed_facts=tampered,
        expected_task_contract_fingerprint=auth.task_contract_fingerprint,
        expected_authorization_fingerprint=execution_authorization_fingerprint(auth),
        expected_worker_report_fingerprint=worker_report_fingerprint(worker),
        expected_observed_facts_fingerprint=observed_post_run_facts_fingerprint(
            tampered
        ),
        expected_validation_receipt_fingerprints=tuple(
            sorted(
                validation_receipt_fingerprint(item)
                for item in honest.validation_receipts
            )
        ),
    )
    result = reconcile_post_run(forged)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_VALIDATION_RECEIPT_FINGERPRINT in result.inconsistencies


def test_ac_a_changed_final_state_makes_every_receipt_stale():
    coherent = reconcile(
        authorization(), report(), facts(), bind_receipts=True
    )
    assert coherent.status == STATUS_RECONCILED

    moved = facts(final_state_fingerprint=S2)
    result = reconcile(authorization(), report(), moved, bind_receipts=True)

    assert result.status == STATUS_INCOMPLETE
    assert INCONSISTENT_VALIDATION_STALE in result.inconsistencies
    assert result.final_state_binding.validated_state_current is False


def test_a_broken_state_chain_is_an_inconsistent_fact_set():
    stalled = facts(post_execution_state_fingerprint=S0, final_state_fingerprint=S0)
    result = reconcile(authorization(), report(), stalled)

    assert result.status == STATUS_INCONSISTENT_INPUT
    assert result.change_findings == ()
    assert result.validation_findings == ()


# ── §28 renames ───────────────────────────────────────────────────────────────

def test_a_rename_is_never_inferred_from_a_delete_plus_an_add():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(path=SESSION, authority=PATH_AUTHORITY_WRITABLE),
        )
    )
    worker = report(
        declared_changes=(
            DeclaredChange(
                path=SESSION, change_kind=CHANGE_RENAMED, from_path=ROUTER
            ),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_DELETED,
                before_sha256=digest("router-0"),
            ),
            ObservedChange(
                path=SESSION,
                change_kind=CHANGE_ADDED,
                after_sha256=digest("router-0"),
            ),
        )
    )
    result = reconcile(auth, worker, observed)

    assert finding_for(result, ROUTER).classification == CLASSIFICATION_UNDECLARED
    assert finding_for(result, SESSION).classification == CLASSIFICATION_KIND_MISMATCH
    assert result.status == STATUS_SUSPICIOUS


def test_an_authoritative_rename_is_preserved_when_the_collector_supports_it():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(path=SESSION, authority=PATH_AUTHORITY_WRITABLE),
        )
    )
    worker = report(
        declared_changes=(
            DeclaredChange(
                path=SESSION, change_kind=CHANGE_RENAMED, from_path=ROUTER
            ),
        )
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=SESSION,
                change_kind=CHANGE_RENAMED,
                from_path=ROUTER,
                after_sha256=digest("router-0"),
            ),
        ),
        rename_detection_supported=True,
    )
    result = reconcile(auth, worker, observed)

    assert finding_for(result, SESSION).classification == CLASSIFICATION_MATCHED
    assert result.observed_change_summary.renamed_paths == (SESSION,)
    assert result.status == STATUS_RECONCILED


def test_a_rename_a_collector_cannot_detect_is_an_inconsistent_fact_set():
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=SESSION,
                change_kind=CHANGE_RENAMED,
                from_path=ROUTER,
                after_sha256=digest("router-0"),
            ),
        ),
        rename_detection_supported=False,
    )
    result = reconcile(authorization(), report(), observed)

    assert result.status == STATUS_INCONSISTENT_INPUT


# ── §55 determinism ───────────────────────────────────────────────────────────

def test_unordered_path_and_receipt_input_canonicalizes():
    paths = (
        AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
        AuthorizedPath(path=SESSION, authority=PATH_AUTHORITY_WRITABLE),
        AuthorizedPath(path=NOTES, authority=PATH_AUTHORITY_WRITABLE),
    )
    expectations = (
        ValidationExpectation(
            validation_id="V-unit",
            validation_kind=VALIDATION_UNIT_TESTS,
            required=True,
            target_scope=("tests/test_router.py",),
        ),
        ValidationExpectation(
            validation_id="V-static",
            validation_kind=VALIDATION_STATIC_CHECK,
            required=False,
        ),
    )
    declared = (
        DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
        DeclaredChange(path=SESSION, change_kind=CHANGE_MODIFIED),
    )
    changes = (
        ObservedChange(
            path=ROUTER,
            change_kind=CHANGE_MODIFIED,
            before_sha256=digest("router-0"),
            after_sha256=digest("router-1"),
        ),
        ObservedChange(
            path=SESSION,
            change_kind=CHANGE_MODIFIED,
            before_sha256=digest("session-0"),
            after_sha256=digest("session-1"),
        ),
    )
    receipts = (receipt(), receipt(receipt_id="RECEIPT-2", validation_id="V-static",
                                   validation_kind=VALIDATION_STATIC_CHECK,
                                   target_scope=()))

    forward = reconcile(
        authorization(
            authorized_paths=paths, validation_expectations=expectations
        ),
        report(declared_changes=declared),
        facts(observed_changes=changes, validation_receipts=receipts),
        bind_receipts=True,
    )
    reverse = reconcile(
        authorization(
            authorized_paths=tuple(reversed(paths)),
            validation_expectations=tuple(reversed(expectations)),
        ),
        report(declared_changes=tuple(reversed(declared))),
        facts(
            observed_changes=tuple(reversed(changes)),
            validation_receipts=tuple(reversed(receipts)),
        ),
        bind_receipts=True,
    )

    assert forward.reconciliation_fingerprint == reverse.reconciliation_fingerprint
    assert render_post_run_reconciliation_json(
        forward
    ) == render_post_run_reconciliation_json(reverse)


def test_the_same_fact_set_reconciles_byte_identically():
    first = reconcile(authorization(), report(), facts())
    second = reconcile(authorization(), report(), facts())

    assert render_post_run_reconciliation_json(
        first
    ) == render_post_run_reconciliation_json(second)


# ── §56 DeepSeek-style execution regression ───────────────────────────────────

def deepseek_scenario():
    auth = authorization(
        authorized_paths=(
            AuthorizedPath(path=ROUTER, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(path=SESSION, authority=PATH_AUTHORITY_WRITABLE),
            AuthorizedPath(
                path=CONFIG,
                authority=PATH_AUTHORITY_FORBIDDEN,
                forbidden_reason=FORBIDDEN_SENSITIVE,
            ),
        )
    )
    worker = report(
        declared_status=WORKER_CLAIM_SUCCESS,
        declared_changes=(
            DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
            DeclaredChange(path=SESSION, change_kind=CHANGE_MODIFIED),
        ),
    )
    observed = facts(
        observed_changes=(
            ObservedChange(
                path=ROUTER,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("router-0"),
                after_sha256=digest("router-1"),
            ),
            ObservedChange(
                path=SESSION,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("session-0"),
                after_sha256=digest("session-1"),
            ),
            ObservedChange(
                path=CONFIG,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("config-0"),
                after_sha256=digest("config-1"),
            ),
        ),
        # The suite passed before config.py was touched.
        validation_receipts=(receipt(state_fingerprint=S1),),
        post_execution_state_fingerprint=S1,
        final_state_fingerprint=S2,
    )
    return auth, worker, observed


def test_deepseek_style_run_is_blocked_without_any_semantic_reviewer():
    result = reconcile(*deepseek_scenario(), bind_receipts=True)

    assert CONFIG in [item.path for item in result.undeclared_changes]
    assert CONFIG in [item.path for item in result.forbidden_changes]
    assert INCONSISTENT_UNDECLARED_CHANGE in result.inconsistencies
    assert INCONSISTENT_FORBIDDEN_CHANGE in result.inconsistencies
    assert INCONSISTENT_VALIDATION_STALE in result.inconsistencies
    assert INCONSISTENT_WORKER_SUCCESS_CLAIM in result.inconsistencies
    assert result.worker_status_consistent is False
    assert result.status == STATUS_BLOCKED

    guardrails = result.as_dict()["guardrails"]
    assert guardrails["model_called"] is False
    assert guardrails["semantic_goal_review_performed"] is False
    assert guardrails["validation_executed"] is False


# ── §57 a persuasive note cannot override the facts ───────────────────────────

def test_a_polished_completion_note_cannot_override_objective_facts():
    auth, _worker, observed = deepseek_scenario()
    polished = report(
        declared_status=WORKER_CLAIM_SUCCESS,
        declared_changes=(
            DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
            DeclaredChange(path=SESSION, change_kind=CHANGE_MODIFIED),
        ),
        declared_limitations=(
            "Refactor is complete, fully tested and ready for review.",
        ),
        declared_unresolved_items=("None; everything looks good.",),
    )
    result = reconcile(auth, polished, observed)

    assert result.status == STATUS_BLOCKED
    assert result.worker_status_consistent is False
    # The prose is carried verbatim for CHECK.2 but discharges nothing.
    payload = json.loads(render_post_run_reconciliation_json(result))
    assert "everything looks good" not in json.dumps(payload["views"])


# ── §58 no success laundering ─────────────────────────────────────────────────

def test_passing_tests_cannot_launder_a_forbidden_path_violation():
    auth, worker, observed = deepseek_scenario()
    fresh = ObservedPostRunFacts(
        facts_id=observed.facts_id,
        execution_run_id=observed.execution_run_id,
        repository_id=observed.repository_id,
        pre_execution_state_fingerprint=observed.pre_execution_state_fingerprint,
        post_execution_state_fingerprint=S2,
        final_state_fingerprint=S2,
        observed_changes=observed.observed_changes,
        validation_receipts=(receipt(state_fingerprint=S2),),
    )
    result = reconcile(auth, worker, fresh)

    assert validation_for(result, "V-unit").coverage == COVERAGE_SATISFIED
    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_FORBIDDEN_CHANGE in result.inconsistencies


def test_reconciled_never_serializes_a_goal_or_correctness_claim():
    payload = json.loads(
        render_post_run_reconciliation_json(
            reconcile(authorization(), report(), facts())
        )
    )
    rendered = json.dumps(payload)

    assert payload["status"] == STATUS_RECONCILED
    # No key anywhere in the receipt asserts semantic correctness.  Honest
    # *negative* authority keys such as ``implementation_correctness_authority``
    # are permitted, so the scan is over key names, never raw substrings.
    def walk_keys(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from walk_keys(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk_keys(value)

    keys = set(walk_keys(payload))
    for banned in (
        "goal_satisfied",
        "implementation_correct",
        "semantically_correct",
        "implementation_good",
        "overall_success",
        "tests_passed",
    ):
        assert banned not in keys
    assert "goal_satisfied" not in rendered
    assert payload["authority"]["semantic_goal_review_authority"] is False
    assert payload["authority"]["implementation_correctness_authority"] is False
    assert payload["authority"]["final_success_authority"] is False
    assert payload["guardrails"]["final_success_declared"] is False
    assert payload["reconciled_meaning"] == RECONCILED_MEANING
    assert "does not mean" in RECONCILED_MEANING


# ── §41 / §42 / §43 boundary shape ────────────────────────────────────────────

def test_one_request_yields_one_bounded_result():
    result = reconcile(authorization(), report(), facts())

    assert result.worker_report_fingerprint == worker_report_fingerprint(report())
    assert result.observed_facts_fingerprint == observed_post_run_facts_fingerprint(
        facts()
    )
    assert result.execution_authorization_fingerprint == (
        execution_authorization_fingerprint(authorization())
    )


def test_authority_is_narrow_and_denies_every_other_power():
    authority = reconciliation_authority(post_run_reconciliation_authority=True)

    assert authority["post_run_reconciliation_authority"] is True
    assert authority["human_approval_required"] is True
    for denied in (
        "semantic_goal_review_authority",
        "implementation_correctness_authority",
        "final_success_authority",
        "merge_authority",
        "patch_authority",
        "write_authority",
        "repository_read_authority",
        "repository_traversal_authority",
        "validation_execution_authority",
        "command_execution_authority",
        "model_selection_authority",
        "provider_selection_authority",
        "final_response_authority",
    ):
        assert authority[denied] is False


def test_guardrails_report_only_work_that_was_performed():
    guardrails = reconcile(authorization(), report(), facts()).as_dict()["guardrails"]

    for performed in (
        "worker_report_reconciled",
        "change_scope_checked",
        "declared_vs_observed_compared",
        "validation_receipts_checked",
        "validation_freshness_checked",
        "final_state_binding_checked",
        "facts_collected_externally",
    ):
        assert guardrails[performed] is True
    for denied in (
        "repository_traversed",
        "source_content_read",
        "validation_executed",
        "patch_applied",
        "files_modified",
        "semantic_goal_review_performed",
        "model_called",
        "conflict_resolved",
        "merge_performed",
        "final_success_declared",
    ):
        assert guardrails[denied] is False


def test_guardrails_do_not_claim_a_freshness_check_that_never_ran():
    guardrails = reconcile(
        authorization(), report(), facts(validation_receipts=())
    ).as_dict()["guardrails"]

    assert guardrails["validation_freshness_checked"] is False
    assert guardrails["declared_vs_observed_compared"] is True


def test_guardrail_helper_cannot_be_forced_to_claim_a_denied_power():
    guardrails = reconciliation_guardrails(
        worker_report_reconciled=True,
        change_scope_checked=True,
        declared_vs_observed_compared=True,
        validation_receipts_checked=True,
        validation_freshness_checked=True,
        final_state_binding_checked=True,
        facts_collected_externally=True,
    )
    assert guardrails["validation_executed"] is False
    assert guardrails["patch_applied"] is False
    assert guardrails["semantic_goal_review_performed"] is False


# ── Record validation ─────────────────────────────────────────────────────────

def test_a_forbidden_path_must_state_a_bounded_reason():
    with pytest.raises(ValueError):
        AuthorizedPath(path=CONFIG, authority=PATH_AUTHORITY_FORBIDDEN)
    with pytest.raises(ValueError):
        AuthorizedPath(
            path=CONFIG,
            authority=PATH_AUTHORITY_WRITABLE,
            forbidden_reason=FORBIDDEN_SENSITIVE,
        )


def test_an_expansion_receipt_may_only_grant_a_write_bearing_authority():
    with pytest.raises(ValueError):
        PathExpansionReceipt(
            path=SESSION,
            authority=PATH_AUTHORITY_SUPPORTING_READ_ONLY,
            approval_receipt_sha256=digest("approval"),
        )


def test_observed_change_digests_must_match_the_change_kind():
    with pytest.raises(ValueError):
        ObservedChange(path=ROUTER, change_kind=CHANGE_ADDED)
    with pytest.raises(ValueError):
        ObservedChange(
            path=ROUTER, change_kind=CHANGE_MODIFIED, after_sha256=digest("x")
        )
    with pytest.raises(ValueError):
        ObservedChange(
            path=ROUTER, change_kind=CHANGE_DELETED, after_sha256=digest("x")
        )


def test_paths_must_be_canonical_repository_relative_spellings():
    for bad in ("/etc/passwd", "../outside.py", "core\\router.py", ""):
        with pytest.raises((ValueError, TypeError)):
            ObservedChange(
                path=bad,
                change_kind=CHANGE_MODIFIED,
                before_sha256=digest("a"),
                after_sha256=digest("b"),
            )


def test_a_declared_change_may_not_repeat_a_path():
    with pytest.raises(ValueError):
        report(
            declared_changes=(
                DeclaredChange(path=ROUTER, change_kind=CHANGE_MODIFIED),
                DeclaredChange(path=ROUTER, change_kind=CHANGE_ADDED),
            )
        )


def test_reconcile_rejects_an_untyped_request():
    with pytest.raises(TypeError):
        reconcile_post_run({"authorization": authorization()})
