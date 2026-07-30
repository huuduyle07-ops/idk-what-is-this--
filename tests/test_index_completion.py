"""INDEX.1D.2C honest persistence-completion contract tests.

The completion module is deliberately pure.  These tests supply immutable
evidence, exercise identity/completion composition, and prove that neither
manifest persistence nor production delta execution is wired here.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path

import pytest

from core import code_dna as code_dna_module
import core.index_completion as completion
from core.repository_identity_state import (
    DECISION_SAME_PROJECT,
    IDENTITY_STATUS_ARCHIVED,
    IDENTITY_STATUS_BLOCKED,
    SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
    SIGNAL_PRIMARY_INTERFACE_CHANGED,
    apply_human_identity_decision,
    apply_major_change_candidate,
    classify_major_change_candidate,
    derive_canonical_identity_permissions,
    initialize_repository_identity_state,
    validate_repository_identity_state,
)


ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = ROOT / "core" / "index_completion.py"
INDEXER_PATH = ROOT / "core" / "indexer.py"
CONFIRMED_AT = "2026-07-28T01:00:00+00:00"
DETECTED_AT = "2026-07-28T02:00:00+00:00"


def _initial(repo: Path):
    return initialize_repository_identity_state(repo)


def _confirmed(repo: Path):
    result = apply_human_identity_decision(
        _initial(repo),
        DECISION_SAME_PROJECT,
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="Confirmed for honest completion contract tests.",
        confirmed_project_tag="cattus",
    )
    assert result.valid, result.errors
    assert validate_repository_identity_state(result.state).valid
    return result.state


def _major_pending(repo: Path):
    decision = classify_major_change_candidate(
        signals=[
            SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
            SIGNAL_PRIMARY_INTERFACE_CHANGED,
        ]
    )
    result = apply_major_change_candidate(
        _confirmed(repo),
        decision,
        detected_at=DETECTED_AT,
        evidence=[
            "Entrypoint and primary interface changed in supplied evidence."
        ],
    )
    assert result.valid, result.errors
    assert validate_repository_identity_state(result.state).valid
    return result.state


def _terminal_identity(repo: Path, status: str):
    confirmed = _confirmed(repo)
    terminal = replace(
        confirmed,
        identity_status=status,
        human_confirmation_required=status == IDENTITY_STATUS_BLOCKED,
        permissions=derive_canonical_identity_permissions(status),
        state_revision=confirmed.state_revision + 1,
    )
    validation = validate_repository_identity_state(terminal)
    assert validation.valid, validation.errors
    return terminal


def _persisted_file(
    file_path: str = "core/example.py",
    *,
    action: str = completion.FILE_ACTION_MODIFIED,
    embedding_status: str = completion.EMBEDDING_STATUS_EMBEDDED,
    embedding_required: bool | None = None,
) -> completion.FilePersistenceEvidence:
    required = (
        embedding_status != completion.EMBEDDING_STATUS_NOT_REQUIRED
        if embedding_required is None
        else embedding_required
    )
    return completion.FilePersistenceEvidence(
        file_path=file_path,
        action=action,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=embedding_status,
        persistence_status=completion.FILE_PERSISTENCE_PERSISTED,
        embedding_required=required,
    )


def _deleted_file(
    file_path: str = "core/removed.py",
) -> completion.FilePersistenceEvidence:
    return completion.FilePersistenceEvidence(
        file_path=file_path,
        action=completion.FILE_ACTION_DELETED,
        processing_status=completion.PROCESSING_STATUS_NOT_REQUIRED,
        embedding_status=completion.EMBEDDING_STATUS_NOT_REQUIRED,
        persistence_status=completion.FILE_PERSISTENCE_DELETED,
    )


def _unchanged_file(
    file_path: str = "core/unchanged.py",
) -> completion.FilePersistenceEvidence:
    return completion.FilePersistenceEvidence(
        file_path=file_path,
        action=completion.FILE_ACTION_UNCHANGED,
        processing_status=completion.PROCESSING_STATUS_NOT_REQUIRED,
        embedding_status=completion.EMBEDDING_STATUS_NOT_REQUIRED,
        persistence_status=(
            completion.FILE_PERSISTENCE_SKIPPED_UNCHANGED
        ),
    )


def _processing_ok() -> completion.ProcessingEvidence:
    return completion.ProcessingEvidence(attempted=True, ok=True)


def _persistence_ok(
    *files: completion.FilePersistenceEvidence,
    identity_state=None,
) -> completion.PersistenceEvidence:
    outcomes = files or (_persisted_file(),)
    return completion.PersistenceEvidence(
        required=True,
        enabled=True,
        attempted=True,
        ok=True,
        index_scope=(
            identity_state.active_index_scope
            if identity_state is not None
            else None
        ),
        files=outcomes,
        required_files=tuple(item.file_path for item in outcomes),
    )


def _reconciliation_ok(
    identity_state=None,
) -> completion.ReconciliationEvidence:
    return completion.ReconciliationEvidence(
        required=True,
        attempted=True,
        ok=True,
        index_scope=(
            identity_state.active_index_scope
            if identity_state is not None
            else None
        ),
        deleted_units=2,
        deleted_dependencies=3,
        preserved_external_targets=4,
    )


def _classify_success(
    identity_state,
    *,
    files: tuple[completion.FilePersistenceEvidence, ...] = (),
    auxiliary=None,
    run_id: str | None = "run-1",
    observed_state_id: str | None = "state-1",
) -> completion.IndexCompletionDecision:
    return completion.classify_index_completion(
        identity_state=identity_state,
        processing=_processing_ok(),
        persistence=_persistence_ok(
            *files,
            identity_state=identity_state,
        ),
        reconciliation=_reconciliation_ok(identity_state),
        auxiliary=auxiliary,
        completion_run_id=run_id,
        observed_state_id=observed_state_id,
    )


def _skipped_reconciliation(
    reason: str,
) -> completion.ReconciliationEvidence:
    return completion.ReconciliationEvidence(
        required=True,
        attempted=False,
        ok=False,
        skipped_reason=reason,
    )


def _persistence_failure_decision(
    identity_state,
    file_evidence: completion.FilePersistenceEvidence,
    *,
    failure_stage: str,
) -> completion.IndexCompletionDecision:
    return completion.classify_index_completion(
        identity_state=identity_state,
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=False,
            index_scope=identity_state.active_index_scope,
            files=(file_evidence,),
            required_files=(file_evidence.file_path,),
            failure_stage=failure_stage,
        ),
        reconciliation=_skipped_reconciliation(
            "required persistence failed"
        ),
        completion_run_id="failed-run",
    )


def _manifest_for(
    decision: completion.IndexCompletionDecision,
    *,
    committed: bool,
    completion_run_id: str,
    applied_manifest_run_id: str,
    observed_state_id: str,
    applied_state_id: str,
) -> completion.AppliedManifestEvidence:
    return completion.AppliedManifestEvidence(
        committed=committed,
        completion_run_id=completion_run_id,
        applied_manifest_run_id=applied_manifest_run_id,
        observed_state_id=observed_state_id,
        applied_state_id=applied_state_id,
        repository_id=decision.repository_id,
        active_index_scope=decision.active_index_scope,
        architecture_epoch=decision.architecture_epoch,
        identity_state_revision=decision.identity_state_revision,
    )


def test_stable_completion_status_vocabulary_is_exact():
    assert completion.COMPLETION_STATUSES == (
        "complete",
        "complete_with_warnings",
        "processing_failed",
        "persistence_failed",
        "reconciliation_failed",
        "identity_blocked",
        "persistence_disabled",
        "persistence_not_attempted",
        "auxiliary_failed",
        "invalid_completion_evidence",
    )


def test_full_success_is_trusted_but_does_not_claim_current(tmp_path):
    decision = _classify_success(
        _confirmed(tmp_path),
        files=(
            _persisted_file(),
            _deleted_file(),
            _unchanged_file(),
        ),
    )

    assert decision.status == completion.STATUS_COMPLETE
    assert decision.processing_ok is True
    assert decision.persistence_required is True
    assert decision.persistence_attempted is True
    assert decision.persistence_ok is True
    assert decision.reconciliation_required is True
    assert decision.reconciliation_attempted is True
    assert decision.reconciliation_ok is True
    assert decision.trusted_completion is True
    assert decision.manifest_advance_allowed is True
    assert decision.trusted_current_claim_allowed is False
    assert decision.current_claim_requires_manifest_commit is True
    assert decision.failed_files == ()
    assert decision.evidence_validated is True


def test_processing_failure_blocks_trusted_completion(tmp_path):
    failed_file = completion.FilePersistenceEvidence(
        file_path="core/broken.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PARSE_FAILED,
        embedding_status=completion.EMBEDDING_STATUS_BLOCKED,
        persistence_status=completion.FILE_PERSISTENCE_PARSE_FAILED,
        error_category="parse_error",
        error_message="parser fallback also failed",
    )
    decision = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing=completion.ProcessingEvidence(
            attempted=True,
            ok=False,
            failed_files=("core/broken.py",),
            error_category="parse_error",
            error_message="parser fallback also failed",
        ),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=False,
            ok=False,
            files=(failed_file,),
            required_files=("core/broken.py",),
            failure_stage="processing",
        ),
        reconciliation=_skipped_reconciliation("processing failed"),
    )

    assert decision.status == completion.STATUS_PROCESSING_FAILED
    assert decision.failure_stage == "processing"
    assert decision.failed_files == ("core/broken.py",)
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False


@pytest.mark.parametrize(
    ("file_evidence", "stage"),
    [
        (
            completion.FilePersistenceEvidence(
                file_path="core/embedding.py",
                action=completion.FILE_ACTION_MODIFIED,
                processing_status=completion.PROCESSING_STATUS_PROCESSED,
                embedding_status=completion.EMBEDDING_STATUS_FAILED,
                persistence_status=(
                    completion.FILE_PERSISTENCE_EMBEDDING_FAILED
                ),
                embedding_required=True,
                error_category="embedding_error",
                error_message="embedding provider unavailable",
            ),
            "embedding",
        ),
        (
            completion.FilePersistenceEvidence(
                file_path="core/replacement.py",
                action=completion.FILE_ACTION_MODIFIED,
                processing_status=completion.PROCESSING_STATUS_PROCESSED,
                embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
                persistence_status=(
                    completion.FILE_PERSISTENCE_REPLACEMENT_FAILED
                ),
                error_category="database_error",
                error_message="atomic replacement rolled back",
            ),
            "replacement",
        ),
        (
            completion.FilePersistenceEvidence(
                file_path="core/deleted.py",
                action=completion.FILE_ACTION_DELETED,
                processing_status=(
                    completion.PROCESSING_STATUS_NOT_REQUIRED
                ),
                embedding_status=completion.EMBEDDING_STATUS_NOT_REQUIRED,
                persistence_status=(
                    completion.FILE_PERSISTENCE_DELETION_FAILED
                ),
                error_category="database_error",
                error_message="deleted-file cleanup rolled back",
            ),
            "deletion",
        ),
    ],
)
def test_required_file_persistence_failures_block_completion(
    tmp_path,
    file_evidence,
    stage,
):
    decision = _persistence_failure_decision(
        _confirmed(tmp_path),
        file_evidence,
        failure_stage=stage,
    )

    assert decision.status == completion.STATUS_PERSISTENCE_FAILED
    assert decision.persistence_attempted is True
    assert decision.persistence_ok is False
    assert decision.reconciliation_attempted is False
    assert decision.failure_stage == stage
    assert decision.failed_files == (file_evidence.file_path,)
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False


def test_reconciliation_failure_and_skip_are_independently_visible(tmp_path):
    state = _confirmed(tmp_path)
    failed = completion.classify_index_completion(
        identity_state=state,
        processing=_processing_ok(),
        persistence=_persistence_ok(identity_state=state),
        reconciliation=completion.ReconciliationEvidence(
            required=True,
            attempted=True,
            ok=False,
            index_scope=state.active_index_scope,
            error_category="database_error",
            error_message="scope cleanup rolled back",
        ),
    )
    skipped = completion.classify_index_completion(
        identity_state=state,
        processing=_processing_ok(),
        persistence=_persistence_ok(identity_state=state),
        reconciliation=_skipped_reconciliation(
            "reconciliation was not dispatched"
        ),
    )

    assert failed.status == completion.STATUS_RECONCILIATION_FAILED
    assert failed.reconciliation_attempted is True
    assert failed.reconciliation_ok is False
    assert skipped.status == completion.STATUS_RECONCILIATION_FAILED
    assert skipped.reconciliation_attempted is False
    assert skipped.reconciliation_skipped_reason == (
        "reconciliation was not dispatched"
    )
    assert not failed.manifest_advance_allowed
    assert not skipped.manifest_advance_allowed


def test_persistence_disabled_is_not_persistent_success(tmp_path):
    decision = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=False,
            attempted=False,
            ok=False,
        ),
        reconciliation=_skipped_reconciliation(
            "persistence_disabled"
        ),
    )

    assert decision.status == completion.STATUS_PERSISTENCE_DISABLED
    assert decision.persistence_required is True
    assert decision.persistence_attempted is False
    assert decision.persistence_ok is False
    assert decision.trusted_completion is False


def test_required_persistence_not_attempted_fails_closed(tmp_path):
    decision = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=False,
            ok=False,
        ),
        reconciliation=_skipped_reconciliation(
            "persistence was never attempted"
        ),
    )

    assert decision.status == (
        completion.STATUS_PERSISTENCE_NOT_ATTEMPTED
    )
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False


def test_embeddings_not_required_can_still_persist_units(tmp_path):
    decision = _classify_success(
        _confirmed(tmp_path),
        files=(
            _persisted_file(
                embedding_status=completion.EMBEDDING_STATUS_NOT_REQUIRED
            ),
        ),
    )

    assert decision.status == completion.STATUS_COMPLETE
    assert decision.file_outcomes[0].embedding_status == "not_required"
    assert decision.persistence_ok is True


@pytest.mark.parametrize(
    "persistence",
    [
        completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=False,
            ok=True,
            files=(_persisted_file(),),
            required_files=("core/example.py",),
        ),
        completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=True,
            files=(
                completion.FilePersistenceEvidence(
                    file_path="core/example.py",
                    action=completion.FILE_ACTION_MODIFIED,
                    processing_status=(
                        completion.PROCESSING_STATUS_PROCESSED
                    ),
                    embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
                    persistence_status=(
                        completion.FILE_PERSISTENCE_REPLACEMENT_FAILED
                    ),
                    error_category="database_error",
                    error_message="replacement failed",
                ),
            ),
            required_files=("core/example.py",),
        ),
    ],
)
def test_contradictory_persistence_success_is_invalid(
    tmp_path,
    persistence,
):
    decision = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing=_processing_ok(),
        persistence=persistence,
        reconciliation=_reconciliation_ok(),
    )

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert decision.evidence_validated is False
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False


def test_persistence_success_with_failure_stage_is_invalid(tmp_path):
    state = _confirmed(tmp_path)
    decision = completion.classify_index_completion(
        identity_state=state,
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=True,
            index_scope=state.active_index_scope,
            files=(_persisted_file(),),
            required_files=("core/example.py",),
            failure_stage="embedding",
        ),
        reconciliation=_reconciliation_ok(state),
    )

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False
    assert any(
        "failure_stage" in reason for reason in decision.reasons
    )


def test_non_string_file_status_equality_shim_is_invalid(tmp_path):
    class PersistedEqualityShim:
        def __eq__(self, other):
            return (
                type(other) is str
                and other == completion.FILE_PERSISTENCE_PERSISTED
            )

        def __hash__(self):
            return hash(completion.FILE_PERSISTENCE_PERSISTED)

    state = _confirmed(tmp_path)
    file_evidence = completion.FilePersistenceEvidence(
        file_path="core/example.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
        persistence_status=PersistedEqualityShim(),
        embedding_required=True,
    )

    decision = completion.classify_index_completion(
        identity_state=state,
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=True,
            index_scope=state.active_index_scope,
            files=(file_evidence,),
            required_files=("core/example.py",),
        ),
        reconciliation=_reconciliation_ok(state),
    )

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False


def test_reconciliation_ok_without_attempt_is_invalid(tmp_path):
    decision = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing=_processing_ok(),
        persistence=_persistence_ok(),
        reconciliation=completion.ReconciliationEvidence(
            required=True,
            attempted=False,
            ok=True,
        ),
    )

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert any(
        "reconciliation ok=true requires attempted=true" in reason
        for reason in decision.reasons
    )


def test_failure_without_concrete_aggregate_evidence_is_invalid(
    tmp_path,
):
    state = _confirmed(tmp_path)
    missing_processing_failure = completion.classify_index_completion(
        identity_state=state,
        processing=completion.ProcessingEvidence(
            attempted=True,
            ok=False,
        ),
        persistence=_persistence_ok(identity_state=state),
        reconciliation=_reconciliation_ok(state),
    )
    missing_persistence_failure = (
        completion.classify_index_completion(
            identity_state=state,
            processing=_processing_ok(),
            persistence=completion.PersistenceEvidence(
                required=True,
                enabled=True,
                attempted=True,
                ok=False,
                index_scope=state.active_index_scope,
                files=(_persisted_file(),),
                required_files=("core/example.py",),
            ),
            reconciliation=_skipped_reconciliation(
                "persistence failed"
            ),
        )
    )
    missing_reconciliation_failure = (
        completion.classify_index_completion(
            identity_state=state,
            processing=_processing_ok(),
            persistence=_persistence_ok(identity_state=state),
            reconciliation=completion.ReconciliationEvidence(
                required=True,
                attempted=True,
                ok=False,
                index_scope=state.active_index_scope,
            ),
        )
    )

    for decision in (
        missing_processing_failure,
        missing_persistence_failure,
        missing_reconciliation_failure,
    ):
        assert decision.status == (
            completion.STATUS_INVALID_COMPLETION_EVIDENCE
        )
        assert decision.evidence_validated is False
        assert decision.trusted_completion is False


def test_attempted_optional_reconciliation_failure_blocks_completion(
    tmp_path,
):
    state = _confirmed(tmp_path)
    decision = completion.classify_index_completion(
        identity_state=state,
        processing=_processing_ok(),
        persistence=_persistence_ok(identity_state=state),
        reconciliation=completion.ReconciliationEvidence(
            required=False,
            attempted=True,
            ok=False,
            index_scope=state.active_index_scope,
            error_category="database_error",
            error_message="optional cleanup attempt failed",
        ),
    )

    assert decision.status == completion.STATUS_RECONCILIATION_FAILED
    assert decision.reconciliation_required is False
    assert decision.reconciliation_attempted is True
    assert decision.reconciliation_ok is False
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False


def test_duplicate_conflicting_file_outcomes_are_invalid(tmp_path):
    persisted = _persisted_file("core/duplicate.py")
    failed = completion.FilePersistenceEvidence(
        file_path="core/duplicate.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
        persistence_status=(
            completion.FILE_PERSISTENCE_REPLACEMENT_FAILED
        ),
        error_category="database_error",
        error_message="replacement failed",
    )
    decision = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=False,
            files=(persisted, failed),
            required_files=("core/duplicate.py",),
        ),
        reconciliation=_skipped_reconciliation(
            "required persistence failed"
        ),
    )

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert any(
        "duplicate or conflicting" in reason
        for reason in decision.reasons
    )


def test_unattempted_files_must_match_aborted_file_evidence(tmp_path):
    failed = completion.FilePersistenceEvidence(
        file_path="core/beta.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
        persistence_status=(
            completion.FILE_PERSISTENCE_REPLACEMENT_FAILED
        ),
        error_category="database_error",
        error_message="replacement failed",
    )
    blocked = completion.FilePersistenceEvidence(
        file_path="core/gamma.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=completion.EMBEDDING_STATUS_BLOCKED,
        persistence_status=completion.FILE_PERSISTENCE_BLOCKED,
        error_category="persistence_aborted",
        error_message="not attempted after prior failure",
    )
    valid = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=False,
            files=(blocked, failed),
            required_files=("core/beta.py", "core/gamma.py"),
            aborted_after_failure=True,
            unattempted_required_files=("core/gamma.py",),
            failure_stage="replacement",
        ),
        reconciliation=_skipped_reconciliation(
            "required persistence failed"
        ),
    )
    contradictory = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=False,
            files=(blocked, failed),
            required_files=("core/beta.py", "core/gamma.py"),
            aborted_after_failure=True,
            unattempted_required_files=("core/beta.py",),
            failure_stage="replacement",
        ),
        reconciliation=_skipped_reconciliation(
            "required persistence failed"
        ),
    )

    assert valid.status == completion.STATUS_PERSISTENCE_FAILED
    assert valid.persistence_aborted_after_failure is True
    assert valid.unattempted_required_files == ("core/gamma.py",)
    assert contradictory.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )


def test_multiple_failure_kinds_preserve_honest_primary_stage(tmp_path):
    state = _confirmed(tmp_path)
    replacement_failed = completion.FilePersistenceEvidence(
        file_path="core/beta.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
        persistence_status=(
            completion.FILE_PERSISTENCE_REPLACEMENT_FAILED
        ),
        error_category="database_error",
        error_message="replacement failed",
    )
    parse_failed = completion.FilePersistenceEvidence(
        file_path="core/gamma.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PARSE_FAILED,
        embedding_status=completion.EMBEDDING_STATUS_BLOCKED,
        persistence_status=completion.FILE_PERSISTENCE_PARSE_FAILED,
        error_category="parse_error",
        error_message="parse failed",
    )

    decision = completion.classify_index_completion(
        identity_state=state,
        processing=completion.ProcessingEvidence(
            attempted=True,
            ok=False,
            failed_files=("core/gamma.py",),
            error_category="parse_error",
            error_message="parse failed",
        ),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=False,
            index_scope=state.active_index_scope,
            files=(replacement_failed, parse_failed),
            required_files=("core/beta.py", "core/gamma.py"),
            failure_stage="replacement",
        ),
        reconciliation=_skipped_reconciliation(
            "required processing or persistence failed"
        ),
    )

    assert decision.status == completion.STATUS_PROCESSING_FAILED
    assert decision.failure_stage == "processing"
    assert decision.failed_files == (
        "core/beta.py",
        "core/gamma.py",
    )
    assert decision.evidence_validated is True


def test_initialization_and_processing_failures_remain_valid_evidence(
    tmp_path,
):
    state = _confirmed(tmp_path)
    parse_failed = completion.FilePersistenceEvidence(
        file_path="core/beta.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PARSE_FAILED,
        embedding_status=completion.EMBEDDING_STATUS_NOT_REQUIRED,
        persistence_status=completion.FILE_PERSISTENCE_PARSE_FAILED,
        error_category="processing_failed",
        error_message="source processing failed",
    )
    unattempted = completion.FilePersistenceEvidence(
        file_path="core/gamma.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=completion.EMBEDDING_STATUS_PENDING,
        persistence_status=completion.FILE_PERSISTENCE_PENDING,
        embedding_required=True,
    )

    decision = completion.classify_index_completion(
        identity_state=state,
        processing=completion.ProcessingEvidence(
            attempted=True,
            ok=False,
            failed_files=("core/beta.py",),
            error_category="processing_failed",
            error_message="source processing failed",
        ),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=False,
            index_scope=state.active_index_scope,
            files=(parse_failed, unattempted),
            required_files=("core/beta.py", "core/gamma.py"),
            aborted_after_failure=True,
            unattempted_required_files=("core/gamma.py",),
            failure_stage="initialization",
            error_category="database_initialization_failed",
            error_message="database initialization failed",
        ),
        reconciliation=_skipped_reconciliation(
            "database initialization failed"
        ),
    )

    assert decision.status == completion.STATUS_PROCESSING_FAILED
    assert decision.failure_stage == "processing"
    assert decision.evidence_validated is True
    assert decision.failed_files == ("core/beta.py",)
    assert decision.unattempted_required_files == ("core/gamma.py",)


def test_unchecked_identity_permissions_and_trusted_input_fail_closed(
    tmp_path,
):
    forged_identity = completion.IdentityCompletionEvidence(
        identity_status="confirmed",
        canonical_mutation_allowed=True,
        reconciliation_allowed=True,
        applied_manifest_advance_allowed=True,
    )
    forged_permissions = completion.classify_index_completion(
        identity_state=forged_identity,
        processing=_processing_ok(),
        persistence=_persistence_ok(),
        reconciliation=_reconciliation_ok(),
    )
    caller_trust = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing={
            "attempted": True,
            "ok": True,
            "trusted_completion": True,
        },
        persistence=_persistence_ok(),
        reconciliation=_reconciliation_ok(),
    )

    assert forged_permissions.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert caller_trust.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert any(
        "unknown fields" in reason for reason in caller_trust.reasons
    )


def test_malformed_full_identity_state_cannot_produce_trust(tmp_path):
    malformed = replace(
        _confirmed(tmp_path),
        state_revision=-1,
    )

    decision = _classify_success(malformed)

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert decision.evidence_validated is False
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False
    assert any(
        "identity_state" in reason for reason in decision.reasons
    )


def test_identity_string_subclass_cannot_bypass_exact_evidence_types(
    tmp_path,
):
    class StringSubclass(str):
        pass

    confirmed = _confirmed(tmp_path)
    malformed = replace(
        confirmed,
        repository_id=StringSubclass(confirmed.repository_id),
    )

    decision = _classify_success(malformed)

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False
    assert any(
        "exact built-in" in reason
        or "repository_id" in reason
        for reason in decision.reasons
    )


def test_identity_validation_reasons_are_credential_redacted(tmp_path):
    state = _confirmed(tmp_path)
    database_url = (
        "postgresql://identity-user:identity-password@"
        "db.example.test/cattus?token=identity-token"
    )
    malformed = replace(
        state,
        identity_status=database_url,
    )

    decision = _classify_success(malformed)
    gate = completion.may_advance_applied_manifest(
        identity_state=malformed,
        completion_decision=_classify_success(state),
    )
    rendered = json.dumps(
        {
            "decision": decision.to_dict(),
            "gate": gate.to_dict(),
        },
        sort_keys=True,
    )

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert gate.allowed is False
    assert database_url not in rendered
    assert "identity-user" not in rendered
    assert "identity-password" not in rendered
    assert "identity-token" not in rendered


@pytest.mark.parametrize(
    "state_factory",
    [
        _initial,
        _major_pending,
        lambda repo: _terminal_identity(
            repo, IDENTITY_STATUS_ARCHIVED
        ),
        lambda repo: _terminal_identity(
            repo, IDENTITY_STATUS_BLOCKED
        ),
    ],
)
def test_nonconfirmed_real_identity_states_block_completion(
    tmp_path,
    state_factory,
):
    decision = _classify_success(state_factory(tmp_path))

    assert decision.status == completion.STATUS_IDENTITY_BLOCKED
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False
    assert decision.failure_stage == "identity"


def test_warning_only_auxiliary_failure_is_trusted_with_warnings(tmp_path):
    identity_state = _confirmed(tmp_path)
    decision = _classify_success(
        identity_state,
        auxiliary=completion.AuxiliaryEvidence(
            component="ProgramGraph presentation build",
            authority=completion.AUXILIARY_AUTHORITY_OUTPUT,
            attempted=True,
            ok=False,
            error_category="graph_error",
            error_message="optional graph rendering failed",
        ),
    )

    assert decision.status == completion.STATUS_COMPLETE_WITH_WARNINGS
    assert decision.auxiliary_graph_ok is False
    assert decision.trusted_completion is True
    assert decision.manifest_advance_allowed is True
    assert decision.warnings == (
        "auxiliary_output_failed: ProgramGraph presentation build",
    )
    gate = completion.may_advance_applied_manifest(
        identity_state=identity_state,
        completion_decision=decision,
    )
    assert gate.allowed is True
    assert gate.status == completion.MANIFEST_GATE_ALLOWED


def test_authoritative_auxiliary_failure_blocks_completion(tmp_path):
    decision = _classify_success(
        _confirmed(tmp_path),
        auxiliary=completion.AuxiliaryEvidence(
            component="canonical repository graph",
            authority=completion.AUXILIARY_AUTHORITY_AUTHORITATIVE,
            attempted=True,
            ok=False,
            error_category="graph_error",
            error_message="authoritative graph persistence failed",
        ),
    )

    assert decision.status == completion.STATUS_AUXILIARY_FAILED
    assert decision.auxiliary_graph_ok is False
    assert decision.trusted_completion is False
    assert decision.manifest_advance_allowed is False


def test_unknown_auxiliary_authority_fails_closed(tmp_path):
    decision = _classify_success(
        _confirmed(tmp_path),
        auxiliary=completion.AuxiliaryEvidence(
            component="mystery graph",
            authority=completion.AUXILIARY_AUTHORITY_UNKNOWN,
            attempted=True,
            ok=False,
            error_category="unknown_error",
            error_message="authority was not classified",
        ),
    )

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert decision.evidence_validated is False
    assert decision.trusted_completion is False


def test_confirmed_identity_and_trusted_completion_allow_manifest_gate(
    tmp_path,
):
    state = _confirmed(tmp_path)
    decision = _classify_success(state)

    gate = completion.may_advance_applied_manifest(
        identity_state=state,
        completion_decision=decision,
    )

    assert gate.allowed is True
    assert gate.status == completion.MANIFEST_GATE_ALLOWED


@pytest.mark.parametrize(
    "state_factory",
    [
        _initial,
        _major_pending,
        lambda repo: _terminal_identity(
            repo, IDENTITY_STATUS_ARCHIVED
        ),
        lambda repo: _terminal_identity(
            repo, IDENTITY_STATUS_BLOCKED
        ),
    ],
)
def test_manifest_gate_revalidates_and_blocks_nonconfirmed_identity(
    tmp_path,
    state_factory,
):
    trusted = _classify_success(_confirmed(tmp_path))
    blocked_state = state_factory(tmp_path)

    gate = completion.may_advance_applied_manifest(
        identity_state=blocked_state,
        completion_decision=trusted,
    )

    assert gate.allowed is False
    assert gate.status == completion.MANIFEST_GATE_IDENTITY_BLOCKED


@pytest.mark.parametrize(
    "decision_factory",
    [
        lambda state: _persistence_failure_decision(
            state,
            completion.FilePersistenceEvidence(
                file_path="core/failure.py",
                action=completion.FILE_ACTION_MODIFIED,
                processing_status=completion.PROCESSING_STATUS_PROCESSED,
                embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
                persistence_status=(
                    completion.FILE_PERSISTENCE_REPLACEMENT_FAILED
                ),
                error_category="database_error",
                error_message="replacement failed",
            ),
            failure_stage="replacement",
        ),
        lambda state: completion.classify_index_completion(
            identity_state=state,
            processing=_processing_ok(),
            persistence=_persistence_ok(identity_state=state),
            reconciliation=completion.ReconciliationEvidence(
                required=True,
                attempted=True,
                ok=False,
                index_scope=state.active_index_scope,
                error_category="database_error",
                error_message="reconciliation failed",
            ),
        ),
        lambda state: completion.classify_index_completion(
            identity_state=state,
            processing=_processing_ok(),
            persistence=completion.PersistenceEvidence(
                required=True,
                enabled=False,
                attempted=False,
                ok=False,
            ),
            reconciliation=_skipped_reconciliation(
                "persistence_disabled"
            ),
        ),
    ],
)
def test_manifest_gate_blocks_incomplete_canonical_work(
    tmp_path,
    decision_factory,
):
    state = _confirmed(tmp_path)
    gate = completion.may_advance_applied_manifest(
        identity_state=state,
        completion_decision=decision_factory(state),
    )

    assert gate.allowed is False
    assert gate.status == completion.MANIFEST_GATE_COMPLETION_BLOCKED


def test_manifest_gate_rejects_unclassified_completion_input(tmp_path):
    gate = completion.may_advance_applied_manifest(
        identity_state=_confirmed(tmp_path),
        completion_decision={"trusted_completion": True},
    )

    assert gate.allowed is False
    assert gate.status == completion.MANIFEST_GATE_INVALID


def test_manifest_gate_rejects_mutated_classified_decision(tmp_path):
    state = _confirmed(tmp_path)
    failed_file = completion.FilePersistenceEvidence(
        file_path="core/failed.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
        persistence_status=completion.FILE_PERSISTENCE_REPLACEMENT_FAILED,
        embedding_required=True,
        error_category="database_error",
        error_message="replacement rolled back",
    )
    failed = _persistence_failure_decision(
        state,
        failed_file,
        failure_stage="replacement",
    )
    forged = replace(
        failed,
        status=completion.STATUS_COMPLETE,
        persistence_ok=True,
        reconciliation_required=False,
        trusted_completion=True,
        manifest_advance_allowed=True,
        failed_files=(),
        file_outcomes=(),
    )

    gate = completion.may_advance_applied_manifest(
        identity_state=state,
        completion_decision=forged,
    )

    assert gate.allowed is False
    assert gate.status == completion.MANIFEST_GATE_INVALID
    assert "reclassified" in gate.reason


def test_manifest_gate_rejects_equality_and_truthiness_shims(tmp_path):
    class TruthyEqualityShim:
        def __bool__(self):
            return True

        def __eq__(self, _other):
            return True

        def __hash__(self):
            return hash(completion.STATUS_COMPLETE)

    class FalsyFailedFiles:
        def __bool__(self):
            return False

        def __iter__(self):
            return iter(("core/failed.py",))

    state = _confirmed(tmp_path)
    failed_file = completion.FilePersistenceEvidence(
        file_path="core/failed.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
        persistence_status=completion.FILE_PERSISTENCE_REPLACEMENT_FAILED,
        embedding_required=True,
        error_category="database_error",
        error_message="replacement rolled back",
    )
    failed = _persistence_failure_decision(
        state,
        failed_file,
        failure_stage="replacement",
    )
    shim = TruthyEqualityShim()
    forged = replace(
        failed,
        status=shim,
        persistence_ok=shim,
        reconciliation_attempted=shim,
        reconciliation_ok=shim,
        trusted_completion=shim,
        manifest_advance_allowed=shim,
        failed_files=FalsyFailedFiles(),
    )

    gate = completion.may_advance_applied_manifest(
        identity_state=state,
        completion_decision=forged,
    )

    assert gate.allowed is False
    assert gate.status == completion.MANIFEST_GATE_INVALID
    assert "reclassified" in gate.reason


def test_manifest_gate_denies_malformed_replaced_nested_outcomes(
    tmp_path,
):
    state = _confirmed(tmp_path)
    trusted = _classify_success(state)
    malformed = replace(
        trusted,
        file_outcomes=(object(),),
    )

    gate = completion.may_advance_applied_manifest(
        identity_state=state,
        completion_decision=malformed,
    )

    assert gate.allowed is False
    assert gate.status == completion.MANIFEST_GATE_INVALID
    assert "safely" in gate.reason


def test_manifest_gate_rejects_completion_from_another_repository(
    tmp_path,
):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    state_a = _confirmed(repo_a)
    state_b = _confirmed(repo_b)
    trusted_a = _classify_success(state_a)

    gate = completion.may_advance_applied_manifest(
        identity_state=state_b,
        completion_decision=trusted_a,
    )

    assert state_a.repository_id != state_b.repository_id
    assert gate.allowed is False
    assert gate.status == completion.MANIFEST_GATE_INVALID
    assert "binding" in gate.reason


@pytest.mark.parametrize(
    ("persistence_scope_matches", "reconciliation_scope_matches"),
    [
        (False, False),
        (True, False),
    ],
)
def test_completion_rejects_scope_or_epoch_mismatch(
    tmp_path,
    persistence_scope_matches,
    reconciliation_scope_matches,
):
    state = _confirmed(tmp_path)
    canonical_scope = state.active_index_scope
    foreign_scope = (
        "repository-index-v2:foreign-repository:epoch-999"
    )
    persistence_scope = (
        canonical_scope
        if persistence_scope_matches
        else foreign_scope
    )
    reconciliation_scope = (
        persistence_scope
        if reconciliation_scope_matches
        else foreign_scope
    )

    decision = completion.classify_index_completion(
        identity_state=state,
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=True,
            index_scope=persistence_scope,
            files=(_persisted_file(),),
            required_files=("core/example.py",),
        ),
        reconciliation=completion.ReconciliationEvidence(
            required=True,
            attempted=True,
            ok=True,
            index_scope=reconciliation_scope,
        ),
    )

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert any(
        "index_scope" in reason for reason in decision.reasons
    )


def test_current_gate_rejects_relabelled_run_and_observed_state(
    tmp_path,
):
    state = _confirmed(tmp_path)
    trusted = _classify_success(
        state,
        run_id="original-run",
        observed_state_id="original-state",
    )
    relabelled = replace(
        trusted,
        completion_run_id="forged-run",
        observed_state_id="forged-state",
    )
    receipt = _manifest_for(
        relabelled,
        committed=True,
        completion_run_id="forged-run",
        applied_manifest_run_id="forged-run",
        observed_state_id="forged-state",
        applied_state_id="forged-state",
    )

    claim = completion.may_claim_repository_intelligence_current(
        identity_state=state,
        completion_decision=relabelled,
        applied_manifest=receipt,
    )

    assert claim.allowed is False
    assert claim.status == completion.CURRENT_CLAIM_COMPLETION_BLOCKED
    assert "reclassified" in claim.reason


def test_required_file_set_and_embedding_requirement_fail_closed(
    tmp_path,
):
    file_evidence = _persisted_file(
        embedding_status=completion.EMBEDDING_STATUS_NOT_REQUIRED,
        embedding_required=True,
    )
    decision = completion.classify_index_completion(
        identity_state=_confirmed(tmp_path),
        processing=_processing_ok(),
        persistence=completion.PersistenceEvidence(
            required=True,
            enabled=True,
            attempted=True,
            ok=True,
            files=(file_evidence,),
            required_files=(
                file_evidence.file_path,
                "core/omitted.py",
            ),
        ),
        reconciliation=_reconciliation_ok(),
    )

    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert any(
        "required_files" in reason for reason in decision.reasons
    )
    assert any(
        "embedding" in reason for reason in decision.reasons
    )


def test_completion_alone_cannot_claim_repository_current(tmp_path):
    state = _confirmed(tmp_path)
    decision = _classify_success(state, run_id="run-current")

    claim = completion.may_claim_repository_intelligence_current(
        identity_state=state,
        completion_decision=decision,
        applied_manifest=_manifest_for(
            decision,
            committed=False,
            completion_run_id="run-current",
            applied_manifest_run_id="run-current",
            observed_state_id="state-1",
            applied_state_id="state-1",
        ),
    )

    assert decision.trusted_current_claim_allowed is False
    assert claim.allowed is False
    assert claim.status == (
        completion.CURRENT_CLAIM_MANIFEST_NOT_COMMITTED
    )


def test_matching_applied_manifest_evidence_allows_current_claim(tmp_path):
    state = _confirmed(tmp_path)
    decision = _classify_success(state, run_id="run-current")
    claim = completion.may_claim_repository_intelligence_current(
        identity_state=state,
        completion_decision=decision,
        applied_manifest=_manifest_for(
            decision,
            committed=True,
            completion_run_id="run-current",
            applied_manifest_run_id="run-current",
            observed_state_id="state-1",
            applied_state_id="state-1",
        ),
    )

    assert claim.allowed is True
    assert claim.status == completion.CURRENT_CLAIM_ALLOWED
    assert claim.completion_run_id == "run-current"
    assert claim.applied_manifest_run_id == "run-current"


@pytest.mark.parametrize(
    ("manifest", "expected_status"),
    [
        (
            completion.AppliedManifestEvidence(
                committed=True,
                completion_run_id="stale-run",
                applied_manifest_run_id="stale-run",
                observed_state_id="state-1",
                applied_state_id="state-1",
            ),
            completion.CURRENT_CLAIM_RUN_MISMATCH,
        ),
        (
            completion.AppliedManifestEvidence(
                committed=True,
                completion_run_id="run-current",
                applied_manifest_run_id="run-current",
                observed_state_id="observed-state",
                applied_state_id="stale-applied-state",
            ),
            completion.CURRENT_CLAIM_STATE_MISMATCH,
        ),
    ],
)
def test_stale_or_mismatched_manifest_evidence_blocks_current_claim(
    tmp_path,
    manifest,
    expected_status,
):
    state = _confirmed(tmp_path)
    decision = _classify_success(state, run_id="run-current")
    manifest = replace(
        manifest,
        repository_id=decision.repository_id,
        active_index_scope=decision.active_index_scope,
        architecture_epoch=decision.architecture_epoch,
        identity_state_revision=decision.identity_state_revision,
    )

    claim = completion.may_claim_repository_intelligence_current(
        identity_state=state,
        completion_decision=decision,
        applied_manifest=manifest,
    )

    assert claim.allowed is False
    assert claim.status == expected_status


def test_current_claim_gate_revalidates_identity(tmp_path):
    trusted = _classify_success(
        _confirmed(tmp_path),
        run_id="run-current",
    )
    claim = completion.may_claim_repository_intelligence_current(
        identity_state=_major_pending(tmp_path),
        completion_decision=trusted,
        applied_manifest=_manifest_for(
            trusted,
            committed=True,
            completion_run_id="run-current",
            applied_manifest_run_id="run-current",
            observed_state_id="state-1",
            applied_state_id="state-1",
        ),
    )

    assert claim.allowed is False
    assert claim.status == completion.CURRENT_CLAIM_IDENTITY_BLOCKED


def test_classifier_is_deterministic_and_does_not_mutate_mapping_inputs(
    tmp_path,
):
    processing = {
        "attempted": True,
        "ok": True,
        "failed_files": [],
        "warnings": ["z warning", "a warning"],
        "error_category": None,
        "error_message": None,
    }
    persistence = {
        "required": True,
        "enabled": True,
        "attempted": True,
        "ok": True,
        "files": [
            _persisted_file("zeta.py").to_dict(),
            _persisted_file("alpha.py").to_dict(),
        ],
        "required_files": ["zeta.py", "alpha.py"],
        "aborted_after_failure": False,
        "unattempted_required_files": [],
        "failure_stage": None,
        "error_category": None,
        "error_message": None,
    }
    reconciliation = {
        "required": True,
        "attempted": True,
        "ok": True,
        "deleted_units": 0,
        "deleted_dependencies": 0,
        "preserved_external_targets": 3,
        "skipped_reason": None,
        "error_category": None,
        "error_message": None,
    }
    auxiliary = [
        {
            "component": "z report",
            "authority": completion.AUXILIARY_AUTHORITY_OUTPUT,
            "attempted": True,
            "ok": True,
            "error_category": None,
            "error_message": None,
        },
        {
            "component": "a graph",
            "authority": completion.AUXILIARY_AUTHORITY_OUTPUT,
            "attempted": True,
            "ok": True,
            "error_category": None,
            "error_message": None,
        },
    ]
    inputs = (processing, persistence, reconciliation, auxiliary)
    snapshot = copy.deepcopy(inputs)
    state = _confirmed(tmp_path)

    first = completion.classify_index_completion(
        identity_state=state,
        processing=processing,
        persistence=persistence,
        reconciliation=reconciliation,
        auxiliary=auxiliary,
        completion_run_id="deterministic-run",
    )
    second = completion.classify_index_completion(
        identity_state=state,
        processing=processing,
        persistence=persistence,
        reconciliation=reconciliation,
        auxiliary=auxiliary,
        completion_run_id="deterministic-run",
    )

    assert inputs == snapshot
    assert first == second
    assert first.to_dict() == second.to_dict()
    assert [item.file_path for item in first.file_outcomes] == [
        "alpha.py",
        "zeta.py",
    ]
    assert [item.component for item in first.auxiliary_outcomes] == [
        "a graph",
        "z report",
    ]
    assert first.warnings == ("a warning", "z warning")


def test_completion_evidence_records_are_frozen():
    evidence = _processing_ok()
    with pytest.raises(FrozenInstanceError):
        evidence.ok = False


def test_credential_bearing_error_evidence_is_sanitized_and_invalid(
    tmp_path,
):
    database_url = (
        "postgresql://index-user:index-password@"
        "db.example.test/cattus?token=index-token"
    )
    failed = completion.FilePersistenceEvidence(
        file_path="core/example.py",
        action=completion.FILE_ACTION_MODIFIED,
        processing_status=completion.PROCESSING_STATUS_PROCESSED,
        embedding_status=completion.EMBEDDING_STATUS_EMBEDDED,
        persistence_status=(
            completion.FILE_PERSISTENCE_REPLACEMENT_FAILED
        ),
        error_category="database_error",
        error_message=f"replacement failed using {database_url}",
    )
    original = copy.deepcopy(failed)

    decision = _persistence_failure_decision(
        _confirmed(tmp_path),
        failed,
        failure_stage="replacement",
    )
    rendered = json.dumps(decision.to_dict(), sort_keys=True)

    assert failed == original
    assert decision.status == (
        completion.STATUS_INVALID_COMPLETION_EVIDENCE
    )
    assert database_url not in rendered
    assert "index-user" not in rendered
    assert "index-password" not in rendered
    assert "index-token" not in rendered
    assert "db.example.test/cattus" in rendered
    assert any(
        "credential-redacted" in reason for reason in decision.reasons
    )


def test_code_dna_write_failure_output_is_credential_redacted(
    monkeypatch,
    capsys,
):
    database_url = (
        "postgresql://dna-user:dna-password@"
        "db.example.test/cattus?token=dna-token"
    )

    class FailingOutput:
        def __truediv__(self, _name):
            return self

        def write_text(self, *_args, **_kwargs):
            raise RuntimeError(
                f"write failed while using {database_url}"
            )

    monkeypatch.setattr(
        "config.get_agent_dir",
        lambda _repo_path: FailingOutput(),
    )

    assert code_dna_module.save_dna("repo", {}) is None
    rendered = capsys.readouterr().out
    assert database_url not in rendered
    assert "dna-user" not in rendered
    assert "dna-password" not in rendered
    assert "dna-token" not in rendered


def test_completion_module_has_no_forbidden_runtime_imports():
    tree = ast.parse(CORE_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    forbidden = {
        "config",
        "database",
        "graph",
        "core.indexer",
        "core.index_manifest",
        "core.index_execution",
        "core.dual_graph_lifecycle",
        "openai",
        "anthropic",
        "requests",
        "httpx",
        "subprocess",
    }
    assert not any(
        name == item or name.startswith(f"{item}.")
        for name in imported
        for item in forbidden
    )


def test_completion_module_performs_no_io_scan_index_or_model_calls():
    tree = ast.parse(CORE_PATH.read_text(encoding="utf-8"))
    forbidden_names = {
        "index_repository",
        "build_graph_from_repo",
        "save_repository_manifest",
        "load_repository_manifest",
        "inspect_repository_delta",
        "build_index_execution_plan",
        "reconcile_code_index_scope",
        "replace_code_index_for_file",
        "delete_code_index_for_file",
        "get_embedding",
        "get_connection",
        "create_pool",
        "open",
        "exec",
        "eval",
        "__import__",
    }
    forbidden_attributes = {
        "walk",
        "scandir",
        "listdir",
        "rglob",
        "glob",
        "iterdir",
        "read_text",
        "write_text",
        "read_bytes",
        "write_bytes",
        "open",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_names
        elif isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_attributes


def test_no_delta_manifest_schema_activation_or_legacy_migration_wiring():
    completion_source = CORE_PATH.read_text(encoding="utf-8")
    indexer_source = INDEXER_PATH.read_text(encoding="utf-8")

    for token in (
        "inspect_repository_delta",
        "build_index_execution_plan",
        "save_repository_manifest",
        "load_repository_manifest",
        "delete_code_index_for_file",
    ):
        assert token not in completion_source
        assert token not in indexer_source

    upper_sources = (
        completion_source.upper(),
        indexer_source.upper(),
    )
    for sql in (
        "ALTER TABLE",
        "CREATE TABLE",
        "DROP TABLE",
        "INSERT INTO",
        "DELETE FROM",
    ):
        assert all(sql not in source for source in upper_sources)

    for token in (
        "ActivationGraph",
        "activation_graph",
        "legacy_namespace",
        "migrate_legacy",
    ):
        assert token not in completion_source
        assert token not in indexer_source
