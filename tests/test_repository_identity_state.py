"""INDEX.1D.2B identity confirmation and architecture-epoch contract tests."""
from __future__ import annotations

import ast
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from core.dual_graph_lifecycle import (
    GRAPH_KIND_ACTIVATION,
    build_dual_graph_lifecycle_contract,
    graph_kind_contract,
)
from core.repository_identity import (
    build_repository_identity,
    derive_repository_index_scope_from_id,
    is_code_index_scope,
)
from core.repository_identity_state import (
    ACTIVATION_ALLOWED_IDENTITY_STATUSES,
    ARTIFACT_KIND,
    DECISION_NEW_ARCHITECTURE_EPOCH,
    DECISION_NEW_PROJECT,
    DECISION_REJECT_OR_DEFER,
    DECISION_SAME_PROJECT,
    IDENTITY_STATE_FILENAME,
    IDENTITY_STATE_LOCK_FILENAME,
    IDENTITY_STATUS_ARCHIVED,
    IDENTITY_STATUS_BLOCKED,
    IDENTITY_STATUS_CONFIRMED,
    IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED,
    IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED,
    IDENTITY_STATUS_UNINITIALIZED,
    LEGACY_MIGRATION_PHASE,
    MAX_ARCHITECTURE_EPOCH,
    MAX_IDENTITY_STATE_BYTES,
    MAX_LEGACY_NAMESPACE_COUNT,
    MAJOR_CHANGE_SIGNAL_IDS,
    PERMISSION_LAYER,
    SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
    SIGNAL_MANUAL_OPERATOR_FLAG,
    SIGNAL_PRIMARY_INTERFACE_CHANGED,
    TRUSTED_COMPLETION_PHASE,
    HumanIdentityDecision,
    IdentityStateError,
    append_legacy_namespace_warnings,
    apply_human_identity_decision,
    apply_major_change_candidate,
    classify_major_change_candidate,
    derive_canonical_identity_permissions,
    get_repository_identity_state_path,
    identity_permission_matrix,
    initialize_repository_identity_state,
    load_repository_identity_state,
    parse_repository_identity_state,
    render_repository_identity_state_json,
    save_repository_identity_state,
    serialize_repository_identity_state,
    validate_identity_state_transition,
    validate_repository_identity_state,
)
import core.repository_identity_state as state_module
import scripts.create_repository_identity_state as script


ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = ROOT / "core" / "repository_identity_state.py"
SCRIPT_PATH = ROOT / "scripts" / "create_repository_identity_state.py"
CONFIRMED_AT = "2026-07-27T12:00:00+00:00"
DETECTED_AT = "2026-07-27T13:00:00+00:00"
RESOLVED_AT = "2026-07-27T14:00:00+00:00"


def _root(tmp_path: Path) -> Path:
    return tmp_path / "canonical-artifacts" / "repository_intelligence"


def _initial(
    repo: Path,
    *,
    candidate_project_tag: str | None = None,
    legacy_namespace_evidence=(),
):
    return initialize_repository_identity_state(
        repo,
        candidate_project_tag=candidate_project_tag,
        legacy_namespace_evidence=legacy_namespace_evidence,
    )


def _confirmed(repo: Path, **over):
    initial = _initial(
        repo,
        candidate_project_tag=over.pop("candidate_project_tag", None),
    )
    values = {
        "confirmed_at": CONFIRMED_AT,
        "confirmed_by": "human",
        "reason": "The operator confirms this semantic project.",
        "confirmed_project_tag": "cattus",
    }
    values.update(over)
    result = apply_human_identity_decision(
        initial,
        DECISION_SAME_PROJECT,
        **values,
    )
    assert result.valid, result.errors
    return result.state


def _major_pending(repo: Path):
    confirmed = _confirmed(repo)
    decision = classify_major_change_candidate(
        signals=[
            SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
            SIGNAL_PRIMARY_INTERFACE_CHANGED,
        ]
    )
    result = apply_major_change_candidate(
        confirmed,
        decision,
        detected_at=DETECTED_AT,
        evidence=["Entrypoint and interface evidence supplied by caller."],
    )
    assert result.valid, result.errors
    return result.state


def _save_initial(repo: Path, root: Path):
    state = _initial(repo)
    result = save_repository_identity_state(
        state,
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=0,
    )
    assert result.ok, result.errors
    return state


def _save_confirmed(repo: Path, root: Path):
    initial = _save_initial(repo, root)
    result = apply_human_identity_decision(
        initial,
        DECISION_SAME_PROJECT,
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="The operator confirms this semantic project.",
        confirmed_project_tag="cattus",
    )
    saved = save_repository_identity_state(
        result.state,
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=initial.state_revision,
    )
    assert saved.ok, saved.errors
    return result.state


# Initial state and project_tag=None semantics.


def test_missing_state_is_uninitialized_and_read_creates_nothing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)

    result = load_repository_identity_state(
        repo,
        repository_intelligence_root=root,
    )

    assert result.exists is False
    assert result.valid is True
    assert result.status == IDENTITY_STATUS_UNINITIALIZED
    assert result.state.project_tag is None
    assert not root.exists()


def test_first_canonical_record_requires_human_confirmation(tmp_path):
    state = _initial(tmp_path)
    assert (
        state.identity_status
        == IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED
    )
    assert state.human_confirmation_required is True
    assert state.project_tag is None
    assert state.confirmation.decision is None


def test_project_tag_none_is_accepted_and_keeps_all_mutations_false(tmp_path):
    state = _initial(tmp_path)
    assert state.project_tag is None
    permissions = state.permissions.to_dict()
    assert all(value is False for value in permissions.values())
    assert (
        derive_canonical_identity_permissions(
            {
                **state.to_dict(),
                "identity_status": IDENTITY_STATUS_CONFIRMED,
                "project_tag": None,
            }
        )
        == derive_canonical_identity_permissions(
            IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED
        )
    )


def test_strict_scope_exists_without_a_project_tag(tmp_path):
    state = _initial(tmp_path)
    assert is_code_index_scope(state.active_index_scope)
    assert state.active_index_scope == (
        derive_repository_index_scope_from_id(state.repository_id)
    )
    assert state.active_index_scope != (state.project_tag or "")


def test_initial_baseline_preserves_1d2a_unsuffixed_scope(tmp_path):
    state = _initial(tmp_path)
    identity = build_repository_identity(tmp_path)
    assert state.architecture_epoch is None
    assert state.active_index_scope == identity.index_scope


# Human confirmation.


def test_same_project_human_decision_confirms_and_records_audit_fields(
    tmp_path,
):
    state = _initial(tmp_path)
    result = apply_human_identity_decision(
        state,
        DECISION_SAME_PROJECT,
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human:operator",
        reason="Confirmed after reviewing the repository identity.",
        confirmed_project_tag="cattus",
    )

    assert result.valid and result.applied
    assert result.state.identity_status == IDENTITY_STATUS_CONFIRMED
    assert result.state.project_tag == "cattus"
    assert result.state.confirmation.to_dict() == {
        "decision": DECISION_SAME_PROJECT,
        "confirmed_at": CONFIRMED_AT,
        "confirmed_by": "human:operator",
        "reason": "Confirmed after reviewing the repository identity.",
    }


def test_candidate_tag_is_not_inferred_as_confirmation(tmp_path):
    state = _initial(tmp_path, candidate_project_tag="candidate")
    result = apply_human_identity_decision(
        state,
        DECISION_SAME_PROJECT,
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="Reviewed but omitted the explicit confirmed label.",
    )

    assert result.valid is False
    assert result.applied is False
    assert result.state == state
    assert state.candidate_project_tag == "candidate"
    assert state.project_tag is None


@pytest.mark.parametrize(
    "decision,confirmed_at,confirmed_by,reason",
    [
        (None, CONFIRMED_AT, "human", "reason"),
        (DECISION_SAME_PROJECT, "", "human", "reason"),
        (DECISION_SAME_PROJECT, CONFIRMED_AT, "model", "reason"),
        (DECISION_SAME_PROJECT, CONFIRMED_AT, "human", ""),
        (
            DECISION_SAME_PROJECT,
            "2026-07-27T12:00:00",
            "human",
            "reason",
        ),
    ],
)
def test_missing_or_nonhuman_decision_cannot_confirm(
    tmp_path,
    decision,
    confirmed_at,
    confirmed_by,
    reason,
):
    state = _initial(tmp_path)
    result = apply_human_identity_decision(
        state,
        decision,
        confirmed_at=confirmed_at,
        confirmed_by=confirmed_by,
        reason=reason,
        confirmed_project_tag="cattus",
    )
    assert result.valid is False
    assert result.state == state


def test_decision_builders_do_not_mutate_inputs(tmp_path):
    signals = [
        {
            "signal_id": SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
            "evidence": ["entrypoint evidence"],
        },
        SIGNAL_PRIMARY_INTERFACE_CHANGED,
    ]
    signals_before = copy.deepcopy(signals)
    state = _initial(tmp_path, candidate_project_tag="candidate")
    state_before = copy.deepcopy(state.to_dict())

    classify_major_change_candidate(signals=signals)
    apply_human_identity_decision(
        state,
        DECISION_SAME_PROJECT,
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="Reviewed identity.",
        confirmed_project_tag="cattus",
    )

    assert signals == signals_before
    assert state.to_dict() == state_before


# Major-change advisory classification and gating.


def test_two_advisory_signals_create_major_change_candidate():
    result = classify_major_change_candidate(
        signals=[
            SIGNAL_PRIMARY_INTERFACE_CHANGED,
            SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
        ]
    )
    assert result.valid
    assert result.major_change_candidate
    assert result.human_confirmation_required
    assert result.automatically_create_new_epoch is False
    assert result.automatically_classify_new_project is False
    assert result.signals == tuple(sorted(result.signals))


def test_one_weak_signal_does_not_force_major_change_by_default():
    result = classify_major_change_candidate(
        signals=[SIGNAL_ENTRYPOINT_FAMILY_CHANGED]
    )
    assert result.valid
    assert result.major_change_candidate is False
    assert result.human_confirmation_required is False


def test_policy_or_manual_flag_can_make_one_signal_decisive():
    policy = classify_major_change_candidate(
        signals=[SIGNAL_ENTRYPOINT_FAMILY_CHANGED],
        thresholds={"minimum_signal_count": 1},
    )
    manual = classify_major_change_candidate(
        signals=[SIGNAL_MANUAL_OPERATOR_FLAG]
    )
    assert policy.major_change_candidate
    assert manual.major_change_candidate


def test_signal_aliases_duplicates_and_order_are_deterministic():
    first = classify_major_change_candidate(
        signals=[
            "primary_surface_change",
            "primary_entrypoint_family_change",
            "primary_surface_change",
        ]
    )
    second = classify_major_change_candidate(
        signals=[
            SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
            SIGNAL_PRIMARY_INTERFACE_CHANGED,
        ]
    )
    assert first.to_dict() == second.to_dict()


def test_unknown_or_oversized_signal_evidence_fails_explicitly():
    unknown = classify_major_change_candidate(signals=["mystery"])
    oversized = classify_major_change_candidate(
        signals=[
            {
                "signal_id": SIGNAL_MANUAL_OPERATOR_FLAG,
                "evidence": ["x" * 513],
            }
        ]
    )
    assert unknown.valid is False
    assert oversized.valid is False
    assert not unknown.major_change_candidate
    assert not oversized.major_change_candidate


def test_major_change_state_disables_reconcile_advance_and_claim(tmp_path):
    pending = _major_pending(tmp_path)
    assert (
        pending.identity_status
        == IDENTITY_STATUS_MAJOR_CHANGE_CONFIRMATION_REQUIRED
    )
    assert pending.major_change.candidate
    assert pending.permissions.reconciliation_allowed is False
    assert pending.permissions.applied_manifest_advance_allowed is False
    assert pending.permissions.trusted_current_claim_allowed is False


def test_major_change_preserves_old_scope_and_activation_availability(
    tmp_path,
):
    confirmed = _confirmed(tmp_path)
    decision = classify_major_change_candidate(
        signals=[
            SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
            SIGNAL_PRIMARY_INTERFACE_CHANGED,
        ]
    )
    pending = apply_major_change_candidate(
        confirmed,
        decision,
        detected_at=DETECTED_AT,
    ).state
    assert pending.active_index_scope == confirmed.active_index_scope
    assert (
        pending.activation_graph_independence.operation_allowed is True
    )
    assert (
        pending.activation_graph_independence.may_confirm_project
        is False
    )


# Epoch behavior and archive preservation.


def test_new_epoch_retains_repository_id_and_derives_new_scope(tmp_path):
    pending = _major_pending(tmp_path)
    result = apply_human_identity_decision(
        pending,
        DECISION_NEW_ARCHITECTURE_EPOCH,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="Runtime and interface assumptions changed materially.",
        new_architecture_epoch=1,
    )

    assert result.valid and result.applied
    assert result.state.repository_id == pending.repository_id
    assert result.state.architecture_epoch == 1
    assert result.state.active_index_scope != pending.active_index_scope
    assert is_code_index_scope(result.state.active_index_scope)


def test_new_epoch_archives_old_scope_without_deletion(tmp_path):
    pending = _major_pending(tmp_path)
    result = apply_human_identity_decision(
        pending,
        DECISION_NEW_ARCHITECTURE_EPOCH,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="Architecture epoch changed after human review.",
        new_architecture_epoch=1,
    )
    archived = result.archived_epoch
    assert archived is not None
    assert archived.identity_status == IDENTITY_STATUS_ARCHIVED
    assert archived.index_scope == pending.active_index_scope
    assert archived.readable is True
    assert archived.writes_allowed is False
    assert archived.reconciliation_allowed is False
    assert archived.deleted is False
    assert result.state.previous_index_scope == pending.active_index_scope


def test_same_project_after_major_change_preserves_epoch_and_scope(tmp_path):
    pending = _major_pending(tmp_path)
    result = apply_human_identity_decision(
        pending,
        DECISION_SAME_PROJECT,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="The architecture remains the same semantic project.",
    )
    assert result.valid
    assert result.state.architecture_epoch == pending.architecture_epoch
    assert result.state.active_index_scope == pending.active_index_scope
    assert result.state.archived_epochs == pending.archived_epochs


@pytest.mark.parametrize(
    "epoch",
    [None, True, False, 0, -1, 2, "1"],
)
def test_epoch_increment_must_be_explicit_positive_and_next(
    tmp_path,
    epoch,
):
    pending = _major_pending(tmp_path)
    result = apply_human_identity_decision(
        pending,
        DECISION_NEW_ARCHITECTURE_EPOCH,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="Epoch request under test.",
        new_architecture_epoch=epoch,
    )
    assert result.valid is False
    assert result.state == pending


def test_new_epoch_is_never_created_from_initial_state(tmp_path):
    initial = _initial(tmp_path)
    result = apply_human_identity_decision(
        initial,
        DECISION_NEW_ARCHITECTURE_EPOCH,
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="Attempted to skip initial confirmation.",
        confirmed_project_tag="cattus",
        new_architecture_epoch=1,
    )
    assert result.valid is False
    assert result.state == initial


def test_initialization_rejects_every_explicit_epoch(tmp_path):
    with pytest.raises(IdentityStateError):
        initialize_repository_identity_state(
            tmp_path,
            architecture_epoch=1,
        )
    epoch_identity = build_repository_identity(
        tmp_path,
        architecture_epoch=1,
    )
    with pytest.raises(IdentityStateError):
        initialize_repository_identity_state(epoch_identity)


def test_epoch_bound_fails_before_lineage_allocation(tmp_path):
    assert MAX_ARCHITECTURE_EPOCH == 1_024
    pending = _major_pending(tmp_path)
    decision = apply_human_identity_decision(
        pending,
        DECISION_NEW_ARCHITECTURE_EPOCH,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="Oversized epoch must fail closed.",
        new_architecture_epoch=MAX_ARCHITECTURE_EPOCH + 1,
    )
    hostile = replace(
        _confirmed(tmp_path),
        architecture_epoch=1_000_000_000,
    )

    assert decision.valid is False
    validation = validate_repository_identity_state(hostile)
    assert validation.valid is False
    assert any("1,024" in error or "1024" in error for error in validation.errors)


def test_repeated_epochs_preserve_full_archive_history(tmp_path):
    first_pending = _major_pending(tmp_path)
    first = apply_human_identity_decision(
        first_pending,
        DECISION_NEW_ARCHITECTURE_EPOCH,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="First architecture epoch.",
        new_architecture_epoch=1,
    ).state
    classifier = classify_major_change_candidate(
        signals=[SIGNAL_MANUAL_OPERATOR_FLAG]
    )
    second_pending = apply_major_change_candidate(
        first,
        classifier,
        detected_at="2026-07-28T12:00:00+00:00",
    ).state
    second = apply_human_identity_decision(
        second_pending,
        DECISION_NEW_ARCHITECTURE_EPOCH,
        confirmed_at="2026-07-28T13:00:00+00:00",
        confirmed_by="human",
        reason="Second architecture epoch.",
        new_architecture_epoch=2,
    ).state

    assert [record.architecture_epoch for record in second.archived_epochs] == [
        None,
        1,
    ]
    assert all(not record.deleted for record in second.archived_epochs)
    assert len({record.index_scope for record in second.archived_epochs}) == 2


# New-project and defer outcomes.


def test_new_project_is_report_only_and_requires_rebinding(tmp_path):
    state = _major_pending(tmp_path)
    before = state.to_dict()
    result = apply_human_identity_decision(
        state,
        DECISION_NEW_PROJECT,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="The directory was repurposed.",
        confirmed_project_tag="different-project",
    )
    assert result.valid and not result.applied
    assert result.rebinding_required
    assert result.outcome == "repository_identity_rebinding_required"
    assert result.state.to_dict() == before
    assert result.state.repository_id == state.repository_id


def test_reject_or_defer_unlocks_no_canonical_permissions(tmp_path):
    state = _major_pending(tmp_path)
    result = apply_human_identity_decision(
        state,
        DECISION_REJECT_OR_DEFER,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="The operator defers the classification.",
    )
    assert result.valid and not result.applied
    assert result.state == state
    assert all(
        value is False for value in result.state.permissions.to_dict().values()
    )


# Pure transition validation and permission matrix.


def test_valid_transitions_are_deterministic(tmp_path):
    initial = _initial(tmp_path)
    confirmed = _confirmed(tmp_path)
    first = validate_identity_state_transition(initial, confirmed)
    second = validate_identity_state_transition(initial, confirmed)
    assert first.allowed
    assert first.to_dict() == second.to_dict()


def test_invalid_transition_is_rejected(tmp_path):
    confirmed = _confirmed(tmp_path)
    initial = _initial(tmp_path)
    result = validate_identity_state_transition(confirmed, initial)
    assert result.allowed is False
    assert result.errors


def test_invalid_identical_state_is_not_an_idempotent_success(tmp_path):
    invalid = replace(_initial(tmp_path), active_index_scope="code-index-bad")
    result = validate_identity_state_transition(invalid, invalid)
    assert result.allowed is False
    assert result.errors


def test_entering_major_review_cannot_rewrite_confirmation_audit(tmp_path):
    confirmed = _confirmed(tmp_path)
    classifier = classify_major_change_candidate(
        signals=[SIGNAL_MANUAL_OPERATOR_FLAG]
    )
    pending = apply_major_change_candidate(
        confirmed,
        classifier,
        detected_at=DETECTED_AT,
    ).state
    rewritten = replace(
        pending,
        confirmation=replace(
            pending.confirmation,
            reason="Rewritten after the fact.",
        ),
    )
    result = validate_identity_state_transition(confirmed, rewritten)
    assert result.allowed is False
    assert any("confirmation" in error for error in result.errors)


def test_major_resolution_preserves_detection_evidence_and_is_fresh(
    tmp_path,
):
    confirmed = _confirmed(tmp_path)
    pending = apply_major_change_candidate(
        confirmed,
        classify_major_change_candidate(
            signals=[SIGNAL_MANUAL_OPERATOR_FLAG]
        ),
        detected_at=CONFIRMED_AT,
        evidence=("Caller-supplied architecture evidence.",),
    ).state
    resolved = apply_human_identity_decision(
        pending,
        DECISION_SAME_PROJECT,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="Explicitly resolved after reviewing supplied evidence.",
    ).state
    erased = replace(
        resolved,
        major_change=replace(resolved.major_change, evidence=()),
    )
    reused_confirmation = replace(
        resolved,
        confirmation=pending.confirmation,
        major_change=replace(
            resolved.major_change,
            resolved_at=pending.confirmation.confirmed_at,
            resolution_decision=pending.confirmation.decision,
        ),
    )

    erased_result = validate_identity_state_transition(pending, erased)
    reused_result = validate_identity_state_transition(
        pending,
        reused_confirmation,
    )

    assert erased_result.allowed is False
    assert any("evidence" in error for error in erased_result.errors)
    assert reused_result.allowed is False
    assert any("fresh" in error for error in reused_result.errors)


def test_major_resolution_cannot_predate_detection(tmp_path):
    confirmed = _confirmed(tmp_path)
    pending = apply_major_change_candidate(
        confirmed,
        classify_major_change_candidate(
            signals=[SIGNAL_MANUAL_OPERATOR_FLAG]
        ),
        detected_at="2030-01-01T00:00:00+00:00",
    ).state
    result = apply_human_identity_decision(
        pending,
        DECISION_SAME_PROJECT,
        confirmed_at="2020-01-01T00:00:00+00:00",
        confirmed_by="human",
        reason="This out-of-order audit must not apply.",
    )
    assert result.valid is False
    assert any("predate" in error for error in result.errors)


def test_confirmed_state_cannot_carry_unresolved_major_history(tmp_path):
    confirmed = _confirmed(tmp_path)
    forged = replace(
        confirmed,
        major_change=replace(
            _major_pending(tmp_path).major_change,
            candidate=False,
        ),
    )
    result = validate_repository_identity_state(forged)
    assert result.valid is False
    assert any("resolution" in error for error in result.errors)


def test_forged_epoch_authority_without_decision_history_fails_closed(
    tmp_path,
):
    pending = _major_pending(tmp_path)
    epoch_one = apply_human_identity_decision(
        pending,
        DECISION_NEW_ARCHITECTURE_EPOCH,
        confirmed_at=RESOLVED_AT,
        confirmed_by="human",
        reason="Explicit epoch transition.",
        new_architecture_epoch=1,
    ).state
    blank_history = replace(
        epoch_one,
        confirmation=replace(
            epoch_one.confirmation,
            decision=DECISION_SAME_PROJECT,
        ),
        major_change=state_module.MajorChangeRecord(),
    )
    baseline_new_epoch = replace(
        _confirmed(tmp_path),
        confirmation=replace(
            _confirmed(tmp_path).confirmation,
            decision=DECISION_NEW_ARCHITECTURE_EPOCH,
        ),
    )

    assert not validate_repository_identity_state(blank_history).valid
    assert not validate_repository_identity_state(baseline_new_epoch).valid
    assert all(
        value is False
        for value in derive_canonical_identity_permissions(
            baseline_new_epoch
        ).to_dict().values()
    )


@pytest.mark.parametrize(
    "terminal_status",
    [IDENTITY_STATUS_ARCHIVED, IDENTITY_STATUS_BLOCKED],
)
def test_archived_and_blocked_states_cannot_reopen_in_place(
    tmp_path,
    terminal_status,
):
    confirmed = _confirmed(tmp_path)
    terminal = replace(
        confirmed,
        identity_status=terminal_status,
        human_confirmation_required=terminal_status
        == IDENTITY_STATUS_BLOCKED,
        permissions=derive_canonical_identity_permissions(terminal_status),
        state_revision=confirmed.state_revision + 1,
    )
    target = replace(
        confirmed,
        state_revision=terminal.state_revision + 1,
    )
    result = validate_identity_state_transition(terminal, target)
    assert result.allowed is False
    assert any("terminal" in error for error in result.errors)


def test_permission_matrix_matches_contract():
    rows = {
        row["identity_status"]: row for row in identity_permission_matrix()
    }
    mutation_fields = (
        "canonical_build_allowed",
        "canonical_refresh_allowed",
        "reconciliation_allowed",
        "applied_manifest_advance_allowed",
    )
    for status, row in rows.items():
        if status == IDENTITY_STATUS_CONFIRMED:
            assert all(row[field] is True for field in mutation_fields)
        else:
            assert all(row[field] is False for field in mutation_fields)
        assert row["trusted_current_claim_allowed"] is False
        assert row["permission_layer"] == PERMISSION_LAYER
        assert row["trusted_completion_required"] is True


def test_confirmed_identity_still_cannot_claim_trusted_current(tmp_path):
    state = _confirmed(tmp_path)
    assert state.permissions.applied_manifest_advance_allowed is True
    assert state.permissions.trusted_current_claim_allowed is False
    assert state.permission_layer == "identity_only"
    assert state.trusted_completion_required is True
    assert state.trusted_completion_phase == TRUSTED_COMPLETION_PHASE


def test_no_state_grants_unscoped_database_authority(tmp_path):
    for state in (
        _initial(tmp_path),
        _confirmed(tmp_path),
        _major_pending(tmp_path),
    ):
        assert is_code_index_scope(state.active_index_scope)
        assert state.active_index_scope not in {"", "global", "shared"}
        assert state.active_index_scope != (state.project_tag or "")


# Persistence, strict parsing, and atomicity.


def test_state_path_uses_bounded_storage_key_under_canonical_root(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    identity = build_repository_identity(repo)
    root = _root(tmp_path)
    path = get_repository_identity_state_path(
        identity,
        repository_intelligence_root=root,
    )
    assert path == root.absolute() / identity.storage_key / IDENTITY_STATE_FILENAME
    assert identity.repository_id != identity.storage_key


def test_atomic_save_and_load_round_trip(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    state = _initial(repo)
    calls = []
    real_replace = state_module.os.replace

    def spy_replace(source, target):
        calls.append((Path(source), Path(target)))
        return real_replace(source, target)

    monkeypatch.setattr(state_module.os, "replace", spy_replace)
    saved = save_repository_identity_state(
        state,
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=0,
    )
    loaded = load_repository_identity_state(
        repo,
        repository_intelligence_root=root,
    )

    assert saved.ok and saved.replaced
    assert loaded.valid and loaded.state == state
    assert len(calls) == 1
    assert calls[0][0].parent == calls[0][1].parent
    assert calls[0][1] == Path(saved.path)
    assert Path(saved.path).read_bytes().endswith(b"\n")
    lock_path = Path(saved.path).with_name(IDENTITY_STATE_LOCK_FILENAME)
    assert lock_path.is_file()
    assert lock_path.read_bytes() == b""


def test_lock_preparation_failure_is_fail_closed(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)

    def fail_preparation(_path):
        raise state_module.IdentityStateStorageError(
            "simulated lock preparation failure"
        )

    monkeypatch.setattr(
        state_module,
        "_prepare_state_directory",
        fail_preparation,
    )
    result = save_repository_identity_state(
        _initial(repo),
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=0,
    )
    assert result.ok is False
    assert any("preparation" in error for error in result.errors)
    assert not root.exists()


def test_deterministic_serialization_and_source_immutability(tmp_path):
    state = _major_pending(tmp_path)
    before = copy.deepcopy(state.to_dict())
    first = serialize_repository_identity_state(state)
    second = serialize_repository_identity_state(state)
    assert first == second
    assert render_repository_identity_state_json(state).encode() == first
    assert state.to_dict() == before
    assert json.loads(first)["artifact_kind"] == ARTIFACT_KIND


def test_malformed_json_returns_explicit_blocked_result(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    identity = build_repository_identity(repo)
    root = _root(tmp_path)
    path = get_repository_identity_state_path(
        identity,
        repository_intelligence_root=root,
    )
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{ definitely not json")

    result = load_repository_identity_state(
        identity,
        repository_intelligence_root=root,
    )

    assert result.exists
    assert result.valid is False
    assert result.status == IDENTITY_STATUS_BLOCKED
    assert result.state.identity_status == IDENTITY_STATUS_BLOCKED
    assert result.errors
    assert path.read_bytes() == b"{ definitely not json"


def test_directory_artifact_and_non_directory_components_fail_soft(
    tmp_path,
):
    cases = []

    repo_target = tmp_path / "repo-target"
    repo_target.mkdir()
    root_target = tmp_path / "root-target"
    target = get_repository_identity_state_path(
        repo_target,
        repository_intelligence_root=root_target,
    )
    target.mkdir(parents=True)
    cases.append((repo_target, root_target))

    repo_root = tmp_path / "repo-root"
    repo_root.mkdir()
    root_file = tmp_path / "root-file"
    root_file.write_text("not a directory", encoding="utf-8")
    cases.append((repo_root, root_file))

    repo_namespace = tmp_path / "repo-namespace"
    repo_namespace.mkdir()
    root_namespace = tmp_path / "root-namespace"
    identity = build_repository_identity(repo_namespace)
    root_namespace.mkdir()
    (root_namespace / identity.storage_key).write_text(
        "not a directory",
        encoding="utf-8",
    )
    cases.append((repo_namespace, root_namespace))

    for repo, root in cases:
        result = load_repository_identity_state(
            repo,
            repository_intelligence_root=root,
        )
        assert result.valid is False
        assert result.status == IDENTITY_STATUS_BLOCKED
        assert result.errors


def test_load_reads_at_most_the_state_size_bound(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    path = get_repository_identity_state_path(
        repo,
        repository_intelligence_root=root,
    )
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * (MAX_IDENTITY_STATE_BYTES + 1))

    result = load_repository_identity_state(
        repo,
        repository_intelligence_root=root,
    )

    assert result.valid is False
    assert any("read bound" in error for error in result.errors)


def test_invalid_repository_or_storage_root_input_fails_soft(tmp_path):
    invalid_repo = load_repository_identity_state("bad\0repo")
    valid_repo = tmp_path / "repo"
    valid_repo.mkdir()
    invalid_root = load_repository_identity_state(
        valid_repo,
        repository_intelligence_root="bad\0root",
    )
    cli = script.run_create_repository_identity_state(
        repo_path=str(valid_repo),
        repository_intelligence_root="bad\0root",
    )

    assert invalid_repo.valid is False
    assert invalid_root.valid is False
    assert cli["ok"] is False


def test_forged_repository_identity_and_root_id_mismatch_are_rejected(
    tmp_path,
):
    identity = build_repository_identity(tmp_path)
    forged_identity = replace(identity, storage_key="repo-forged-0000000000000000")
    with pytest.raises(IdentityStateError):
        initialize_repository_identity_state(forged_identity)

    state = _confirmed(tmp_path)
    mismatched = replace(
        state,
        canonical_root=str((tmp_path / "other").absolute()),
    )
    validation = validate_repository_identity_state(mismatched)
    assert validation.valid is False
    assert any("repository_id" in error for error in validation.errors)


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"schema_version": 1, "schema_version": 1}',
        b'{"value": NaN}',
        b"\xff\xfe",
    ],
)
def test_nonobject_duplicate_nonstandard_or_invalid_utf8_blocks(
    tmp_path,
    payload,
):
    identity = build_repository_identity(tmp_path)
    result = parse_repository_identity_state(
        payload,
        expected_identity=identity,
    )
    assert result.valid is False
    assert result.status == IDENTITY_STATUS_BLOCKED


def test_wrong_repository_id_is_rejected(tmp_path):
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    repo_a.mkdir()
    repo_b.mkdir()
    identity_b = build_repository_identity(repo_b)
    payload = serialize_repository_identity_state(_initial(repo_a))
    result = parse_repository_identity_state(
        payload,
        expected_identity=identity_b,
    )
    assert result.valid is False
    assert any("repository_id" in error for error in result.errors)


def test_tampered_permissions_fail_closed(tmp_path):
    identity = build_repository_identity(tmp_path)
    data = _confirmed(tmp_path).to_dict()
    data["permissions"]["trusted_current_claim_allowed"] = True
    payload = (
        json.dumps(data, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    result = parse_repository_identity_state(
        payload,
        expected_identity=identity,
    )
    assert result.valid is False
    assert any("permissions" in error for error in result.errors)


def test_unsupported_schema_fails_closed(tmp_path):
    identity = build_repository_identity(tmp_path)
    data = _initial(tmp_path).to_dict()
    data["schema_version"] = 999
    result = parse_repository_identity_state(
        json.dumps(data).encode(),
        expected_identity=identity,
    )
    assert result.valid is False
    assert any("schema_version" in error for error in result.errors)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.__setitem__("schema_version", True),
        lambda data: data.__setitem__(
            "human_confirmation_required",
            1,
        ),
        lambda data: data["permissions"].__setitem__(
            "canonical_build_allowed",
            0,
        ),
        lambda data: data["activation_graph_independence"].__setitem__(
            "operation_allowed",
            1,
        ),
        lambda data: data["major_change"].__setitem__("candidate", 0),
    ],
)
def test_json_scalar_types_are_exact_and_fail_closed(tmp_path, mutate):
    identity = build_repository_identity(tmp_path)
    data = _initial(tmp_path).to_dict()
    mutate(data)
    result = parse_repository_identity_state(
        json.dumps(data).encode(),
        expected_identity=identity,
    )
    assert result.valid is False
    assert result.status == IDENTITY_STATUS_BLOCKED


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.__setitem__("project_tag", " cattus"),
        lambda data: data["confirmation"].__setitem__(
            "confirmed_by",
            " human:operator ",
        ),
        lambda data: data["confirmation"].__setitem__(
            "reason",
            " reviewed ",
        ),
    ],
)
def test_persisted_confirmation_text_must_be_canonical(
    tmp_path,
    mutate,
):
    identity = build_repository_identity(tmp_path)
    data = _confirmed(tmp_path).to_dict()
    mutate(data)
    result = parse_repository_identity_state(
        json.dumps(data).encode(),
        expected_identity=identity,
    )
    assert result.valid is False


def test_persisted_legacy_namespace_text_must_be_canonical(tmp_path):
    identity = build_repository_identity(tmp_path)
    data = _initial(
        tmp_path,
        legacy_namespace_evidence=("legacy",),
    ).to_dict()
    data["legacy_namespace_warnings"][0]["namespace"] = " legacy "
    result = parse_repository_identity_state(
        json.dumps(data).encode(),
        expected_identity=identity,
    )
    assert result.valid is False


@pytest.mark.parametrize(
    "status,revision",
    [
        (IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED, 0),
        (IDENTITY_STATUS_CONFIRMED, 1),
    ],
)
def test_persisted_status_requires_minimum_audit_revision(
    tmp_path,
    status,
    revision,
):
    identity = build_repository_identity(tmp_path)
    state = (
        _initial(tmp_path)
        if status == IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED
        else _confirmed(tmp_path)
    )
    data = replace(state, state_revision=revision).to_dict()
    result = parse_repository_identity_state(
        json.dumps(data).encode(),
        expected_identity=identity,
    )
    assert result.valid is False
    assert any("revision" in error for error in result.errors)


def test_persisted_blocked_state_is_never_operable(tmp_path):
    identity = build_repository_identity(tmp_path)
    state = _initial(tmp_path)
    data = replace(
        state,
        identity_status=IDENTITY_STATUS_BLOCKED,
        human_confirmation_required=True,
        state_errors=(),
    ).to_dict()
    result = parse_repository_identity_state(
        json.dumps(data).encode(),
        expected_identity=identity,
    )
    assert result.valid is False
    assert result.status == IDENTITY_STATUS_BLOCKED


def test_permission_derivation_deep_mapping_fails_closed(tmp_path):
    data = _confirmed(tmp_path).to_dict()
    nested = []
    for _ in range(2_000):
        nested = [nested]
    data["state_errors"] = nested
    permissions = derive_canonical_identity_permissions(data)
    assert all(value is False for value in permissions.to_dict().values())


@pytest.mark.parametrize(
    "field,value",
    [
        ("identity_status", []),
        ("state_revision", object()),
        ("previous_index_scope", []),
    ],
)
def test_public_validator_is_total_for_malformed_typed_fields(
    tmp_path,
    field,
    value,
):
    malformed = replace(_initial(tmp_path), **{field: value})
    validation = validate_repository_identity_state(malformed)
    transition = validate_identity_state_transition(malformed, malformed)
    assert validation.valid is False
    assert validation.effective_status == IDENTITY_STATUS_BLOCKED
    assert transition.allowed is False


def test_permission_mapping_with_malformed_warning_fails_closed(tmp_path):
    data = _confirmed(tmp_path).to_dict()
    warning = state_module.LegacyNamespaceWarning(
        namespace="legacy",
        warning=state_module.LEGACY_NAMESPACE_WARNING_TEXT,
    ).to_dict()
    warning["namespace"] = []
    data["legacy_namespace_warnings"] = [warning]
    permissions = derive_canonical_identity_permissions(data)
    assert all(value is False for value in permissions.to_dict().values())


def test_existing_confirmed_state_cannot_be_silently_downgraded(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    confirmed = _save_confirmed(repo, root)
    original = Path(
        get_repository_identity_state_path(
            repo,
            repository_intelligence_root=root,
        )
    ).read_bytes()
    downgraded = _initial(repo)
    saved = save_repository_identity_state(
        downgraded,
        identity=repo,
        repository_intelligence_root=root,
    )
    assert saved.ok is False
    assert Path(saved.path).read_bytes() == original
    assert (
        load_repository_identity_state(
            repo,
            repository_intelligence_root=root,
        ).state
        == confirmed
    )


def test_blocked_artifact_cannot_self_heal(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    path = get_repository_identity_state_path(
        repo,
        repository_intelligence_root=root,
    )
    path.parent.mkdir(parents=True)
    path.write_text("{bad", encoding="utf-8")
    replacement = _initial(repo)
    result = save_repository_identity_state(
        replacement,
        identity=repo,
        repository_intelligence_root=root,
    )
    assert result.ok is False
    assert path.read_text(encoding="utf-8") == "{bad"


def test_stale_revision_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    initial = _save_initial(repo, root)
    confirmed = apply_human_identity_decision(
        initial,
        DECISION_SAME_PROJECT,
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="Confirmed.",
        confirmed_project_tag="cattus",
    ).state
    result = save_repository_identity_state(
        confirmed,
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=0,
    )
    assert result.ok is False
    assert any("stale" in error for error in result.errors)


def test_two_process_first_save_is_one_commit_and_one_stale(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    barrier = tmp_path / "barrier"
    barrier.mkdir()
    helper = tmp_path / "concurrent_identity_writer.py"
    helper.write_text(
        """
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, sys.argv[1])
import core.repository_identity_state as state_module

repo = Path(sys.argv[2])
root = Path(sys.argv[3])
barrier = Path(sys.argv[4])
output = Path(sys.argv[5])
label = sys.argv[6]
state = state_module.initialize_repository_identity_state(repo)
(barrier / f"{label}.ready").write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 15
while len(list(barrier.glob("*.ready"))) < 2:
    if time.monotonic() >= deadline:
        raise RuntimeError("writer barrier timed out")
    time.sleep(0.01)
real_replace = state_module.os.replace
def delayed_replace(source, target):
    time.sleep(0.25)
    return real_replace(source, target)
state_module.os.replace = delayed_replace
result = state_module.save_repository_identity_state(
    state,
    identity=repo,
    repository_intelligence_root=root,
    expected_revision=0,
)
output.write_text(json.dumps(result.to_dict()), encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    outputs = [tmp_path / f"writer-{index}.json" for index in range(2)]
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                str(helper),
                str(ROOT),
                str(repo),
                str(root),
                str(barrier),
                str(outputs[index]),
                str(index),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(2)
    ]
    diagnostics = [
        process.communicate(timeout=20)
        for process in processes
    ]
    assert [process.returncode for process in processes] == [0, 0], diagnostics
    results = [
        json.loads(output.read_text(encoding="utf-8"))
        for output in outputs
    ]

    assert sorted(result["ok"] for result in results) == [False, True]
    failed = next(result for result in results if not result["ok"])
    assert any("stale" in error for error in failed["errors"])
    loaded = load_repository_identity_state(
        repo,
        repository_intelligence_root=root,
    )
    assert loaded.valid
    assert loaded.state.state_revision == 1


def test_replace_failure_preserves_confirmed_bytes_and_cleans_temp(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    confirmed = _save_confirmed(repo, root)
    target = get_repository_identity_state_path(
        repo,
        repository_intelligence_root=root,
    )
    before = target.read_bytes()
    classifier = classify_major_change_candidate(
        signals=[SIGNAL_MANUAL_OPERATOR_FLAG]
    )
    pending = apply_major_change_candidate(
        confirmed,
        classifier,
        detected_at=DETECTED_AT,
    ).state

    def fail_replace(_source, _target):
        raise PermissionError("simulated file lock")

    monkeypatch.setattr(state_module.os, "replace", fail_replace)
    result = save_repository_identity_state(
        pending,
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=confirmed.state_revision,
    )

    assert result.ok is False
    assert target.read_bytes() == before
    assert list(target.parent.glob(".identity_state.*.tmp")) == []


def _make_symlink(link: Path, target: Path, *, directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")


def test_symlinked_namespace_directory_is_rejected_without_escape(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    identity = build_repository_identity(repo)
    root = _root(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    root.mkdir(parents=True)
    _make_symlink(root / identity.storage_key, outside, directory=True)

    result = load_repository_identity_state(
        identity,
        repository_intelligence_root=root,
    )
    saved = save_repository_identity_state(
        _initial(repo),
        identity=identity,
        repository_intelligence_root=root,
    )

    assert result.valid is False
    assert result.status == IDENTITY_STATUS_BLOCKED
    assert saved.ok is False
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert not (outside / IDENTITY_STATE_FILENAME).exists()


def test_symlinked_target_file_is_rejected_without_mutating_target(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    identity = build_repository_identity(repo)
    root = _root(tmp_path)
    target = root / identity.storage_key / IDENTITY_STATE_FILENAME
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text("preserve", encoding="utf-8")
    _make_symlink(target, outside, directory=False)

    result = load_repository_identity_state(
        identity,
        repository_intelligence_root=root,
    )
    assert result.valid is False
    assert result.status == IDENTITY_STATUS_BLOCKED
    assert outside.read_text(encoding="utf-8") == "preserve"


def test_symlinked_lock_file_is_rejected_without_mutating_target(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    identity = build_repository_identity(repo)
    root = _root(tmp_path)
    target = root / identity.storage_key / IDENTITY_STATE_FILENAME
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside.lock"
    outside.write_bytes(b"preserve")
    _make_symlink(
        target.with_name(IDENTITY_STATE_LOCK_FILENAME),
        outside,
        directory=False,
    )

    result = save_repository_identity_state(
        _initial(repo),
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=0,
    )

    assert result.ok is False
    assert outside.read_bytes() == b"preserve"
    assert not target.exists()


def test_hardlinked_lock_file_is_rejected_without_mutating_target(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    identity = build_repository_identity(repo)
    root = _root(tmp_path)
    target = root / identity.storage_key / IDENTITY_STATE_FILENAME
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside-hardlink.lock"
    outside.write_bytes(b"preserve")
    try:
        os.link(
            outside,
            target.with_name(IDENTITY_STATE_LOCK_FILENAME),
        )
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"hardlink creation unavailable: {exc}")

    result = save_repository_identity_state(
        _initial(repo),
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=0,
    )

    assert result.ok is False
    assert outside.read_bytes() == b"preserve"
    assert not target.exists()


def test_nonempty_lock_file_is_rejected_without_state_write(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    identity = build_repository_identity(repo)
    root = _root(tmp_path)
    target = root / identity.storage_key / IDENTITY_STATE_FILENAME
    target.parent.mkdir(parents=True)
    lock_path = target.with_name(IDENTITY_STATE_LOCK_FILENAME)
    lock_path.write_bytes(b"unexpected")

    result = save_repository_identity_state(
        _initial(repo),
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=0,
    )

    assert result.ok is False
    assert lock_path.read_bytes() == b"unexpected"
    assert not target.exists()


# Activation independence, legacy warnings, CLI behavior, and guardrails.


def test_activation_independence_is_pinned_for_all_blocking_statuses():
    rows = {
        row["identity_status"]: row for row in identity_permission_matrix()
    }
    for status in ACTIVATION_ALLOWED_IDENTITY_STATUSES:
        row = rows[status]
        assert row["activation_graph_operation_allowed"] is True
        assert row["canonical_build_allowed"] is False
        assert row["reconciliation_allowed"] is False
        assert row["applied_manifest_advance_allowed"] is False

    metadata = _initial(Path.cwd()).activation_graph_independence
    assert metadata.allowed_identity_statuses == (
        ACTIVATION_ALLOWED_IDENTITY_STATUSES
    )
    assert metadata.operation_allowed
    assert metadata.may_confirm_project is False
    assert metadata.may_create_architecture_epoch is False
    assert metadata.may_advance_canonical_manifest is False
    assert metadata.may_reconcile_canonical_rows is False
    assert metadata.may_change_project_tag is False

    activation = graph_kind_contract(GRAPH_KIND_ACTIVATION)
    assert activation["database_write_allowed"] is False
    assert activation["manifest_advancement_allowed"] is False
    assert activation["reconciliation_allowed"] is False
    lifecycle = build_dual_graph_lifecycle_contract()
    assert (
        lifecycle["canonical_incremental_graph"][
            "while_major_change_confirmation_pending"
        ]["independent_activation_graphs_allowed"]
        is True
    )


def test_legacy_namespaces_are_warning_only_and_preserved(tmp_path):
    evidence = ["legacy-z", "legacy-a", "legacy-z"]
    before = copy.deepcopy(evidence)
    state = _initial(
        tmp_path,
        legacy_namespace_evidence=evidence,
    )
    assert evidence == before
    assert [
        warning.namespace for warning in state.legacy_namespace_warnings
    ] == ["legacy-a", "legacy-z"]
    for warning in state.legacy_namespace_warnings:
        assert warning.preserve
        assert warning.deletion_allowed is False
        assert warning.automatic_epoch_binding_allowed is False
        assert warning.recommended_phase == LEGACY_MIGRATION_PHASE


def test_late_legacy_warnings_are_append_only_and_globally_sorted(tmp_path):
    state = _initial(
        tmp_path,
        legacy_namespace_evidence=("legacy-z",),
    )
    old_warning = state.legacy_namespace_warnings[0]
    transition = append_legacy_namespace_warnings(
        state,
        ("legacy-a", "legacy-z"),
    )

    assert transition.valid and transition.applied
    assert [
        warning.namespace
        for warning in transition.state.legacy_namespace_warnings
    ] == ["legacy-a", "legacy-z"]
    assert transition.state.legacy_namespace_warnings[1] == old_warning
    assert validate_identity_state_transition(
        state,
        transition.state,
    ).allowed

    duplicate = append_legacy_namespace_warnings(
        transition.state,
        ("legacy-z",),
    )
    assert duplicate.valid and not duplicate.applied
    assert duplicate.state == transition.state


def test_legacy_warning_count_is_bounded_across_late_evidence(tmp_path):
    existing = tuple(
        f"legacy-{index:02d}"
        for index in range(MAX_LEGACY_NAMESPACE_COUNT)
    )
    state = _initial(
        tmp_path,
        legacy_namespace_evidence=existing,
    )
    overflow = append_legacy_namespace_warnings(
        state,
        ("legacy-overflow",),
    )
    forged = replace(
        state,
        legacy_namespace_warnings=(
            *state.legacy_namespace_warnings,
            state_module.LegacyNamespaceWarning(
                namespace="legacy-overflow",
                warning=state_module.LEGACY_NAMESPACE_WARNING_TEXT,
            ),
        ),
    )

    assert overflow.valid is False
    assert validate_repository_identity_state(forged).valid is False


def test_script_records_late_legacy_warning_evidence(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    first = script.run_create_repository_identity_state(
        repo_path=str(repo),
        repository_intelligence_root=str(root),
        legacy_namespace_evidence=("legacy-z",),
    )
    second = script.run_create_repository_identity_state(
        repo_path=str(repo),
        repository_intelligence_root=str(root),
        legacy_namespace_evidence=("legacy-a",),
    )

    assert first["ok"] and second["ok"]
    assert second["actions"] == ["legacy_namespace_warnings_recorded"]
    assert [
        warning["namespace"]
        for warning in second["state"]["legacy_namespace_warnings"]
    ] == ["legacy-a", "legacy-z"]


def test_state_persistence_does_not_touch_activation_or_legacy_artifacts(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    activation_file = (
        tmp_path
        / ".agent"
        / "activation_graphs"
        / "task"
        / "metadata.json"
    )
    legacy_file = (
        tmp_path
        / ".agent"
        / "legacy-inventory-namespace"
        / "manifest.json"
    )
    activation_file.parent.mkdir(parents=True)
    legacy_file.parent.mkdir(parents=True)
    activation_file.write_bytes(b"activation-sentinel")
    legacy_file.write_bytes(b"legacy-sentinel")

    state = initialize_repository_identity_state(
        repo,
        legacy_namespace_evidence=("legacy-inventory-namespace",),
    )
    saved = save_repository_identity_state(
        state,
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=0,
    )

    assert saved.ok
    assert activation_file.read_bytes() == b"activation-sentinel"
    assert legacy_file.read_bytes() == b"legacy-sentinel"


def test_secret_shaped_reason_is_rejected(tmp_path):
    state = _initial(tmp_path)
    result = apply_human_identity_decision(
        state,
        DECISION_SAME_PROJECT,
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="password=hunter2",
        confirmed_project_tag="cattus",
    )
    assert result.valid is False
    assert any("credential" in error for error in result.errors)


def test_script_initializes_then_confirms_with_explicit_human_decision(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    result = script.run_create_repository_identity_state(
        repo_path=str(repo),
        repository_intelligence_root=str(root),
        decision=DECISION_SAME_PROJECT,
        project_tag="cattus",
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="Explicit CLI confirmation.",
    )
    assert result["ok"] is True
    assert result["actions"] == [
        IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED,
        IDENTITY_STATUS_CONFIRMED,
    ]
    assert result["state"]["identity_status"] == IDENTITY_STATUS_CONFIRMED


def test_script_new_project_is_report_only(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)
    result = script.run_create_repository_identity_state(
        repo_path=str(repo),
        repository_intelligence_root=str(root),
        decision=DECISION_NEW_PROJECT,
        project_tag="different",
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="Directory was repurposed.",
    )
    assert result["ok"]
    assert result["rebinding_required"]
    loaded = load_repository_identity_state(
        repo,
        repository_intelligence_root=root,
    )
    assert (
        loaded.status
        == IDENTITY_STATUS_INITIAL_CONFIRMATION_REQUIRED
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"candidate_project_tag": "password=secret"},
        {"legacy_namespace_evidence": ("token=secret",)},
    ],
)
def test_script_initial_input_errors_are_deterministic_failures(
    tmp_path,
    kwargs,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    result = script.run_create_repository_identity_state(
        repo_path=str(repo),
        repository_intelligence_root=str(_root(tmp_path)),
        **kwargs,
    )
    assert result["ok"] is False
    assert result["action"] == "initialization_failed"
    assert result["errors"]


def test_state_validation_rejects_secret_shaped_unknown_fields(tmp_path):
    identity = build_repository_identity(tmp_path)
    data = _initial(tmp_path).to_dict()
    data["password"] = "not-allowed"
    result = parse_repository_identity_state(
        json.dumps(data).encode(),
        expected_identity=identity,
    )
    assert result.valid is False
    assert result.status == IDENTITY_STATUS_BLOCKED


def test_core_imports_only_stdlib_and_repository_identity():
    source = CORE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = {
        "__future__",
        "collections",
        "contextlib",
        "dataclasses",
        "datetime",
        "copy",
        "json",
        "os",
        "pathlib",
        "re",
        "stat",
        "tempfile",
        "threading",
        "time",
        "typing",
        "core",
        "fcntl",
        "msvcrt",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name.split(".", 1)[0] in allowed
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".", 1)[0]
            assert top in allowed
            if top == "core":
                assert node.module == "core.repository_identity"


def test_script_imports_only_stdlib_and_identity_state_contract():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    allowed = {
        "__future__",
        "argparse",
        "core",
        "json",
        "pathlib",
        "sys",
        "typing",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name.split(".", 1)[0] in allowed
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".", 1)[0]
            assert top in allowed
            if top == "core":
                assert node.module == "core.repository_identity_state"


def test_no_forbidden_runtime_or_integration_imports():
    trees = [
        ast.parse(CORE_PATH.read_text(encoding="utf-8")),
        ast.parse(SCRIPT_PATH.read_text(encoding="utf-8")),
    ]
    imported = []
    for tree in trees:
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
        "core.retriever",
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


def test_contract_has_no_repository_scan_or_runtime_execution_calls():
    forbidden_names = {
        "index_repository",
        "build_graph_from_repo",
        "save_repository_manifest",
        "load_repository_manifest",
        "reconcile_code_index_scope",
        "get_connection",
        "create_pool",
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
    }
    for source_path in (CORE_PATH, SCRIPT_PATH):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_names
            elif isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_attributes


def test_runtime_state_operations_do_not_walk_or_iterate_repository(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _root(tmp_path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("repository traversal is forbidden")

    monkeypatch.setattr(state_module.os, "walk", forbidden, raising=False)
    monkeypatch.setattr(state_module.os, "scandir", forbidden)
    monkeypatch.setattr(Path, "rglob", forbidden)
    monkeypatch.setattr(Path, "glob", forbidden)
    monkeypatch.setattr(Path, "iterdir", forbidden)

    initial = initialize_repository_identity_state(repo)
    saved = save_repository_identity_state(
        initial,
        identity=repo,
        repository_intelligence_root=root,
        expected_revision=0,
    )
    loaded = load_repository_identity_state(
        repo,
        repository_intelligence_root=root,
    )
    assert saved.ok
    assert loaded.valid


def test_validate_rejects_tampered_active_scope(tmp_path):
    state = _confirmed(tmp_path)
    tampered = replace(state, active_index_scope="shared")
    result = validate_repository_identity_state(tampered)
    assert result.valid is False
    assert result.effective_status == IDENTITY_STATUS_BLOCKED
    assert any("active_index_scope" in error for error in result.errors)


def test_serializing_uninitialized_or_blocked_state_is_forbidden(tmp_path):
    missing = load_repository_identity_state(
        tmp_path,
        repository_intelligence_root=_root(tmp_path),
    ).state
    blocked = replace(
        missing,
        identity_status=IDENTITY_STATUS_BLOCKED,
        human_confirmation_required=True,
        state_errors=("invalid",),
    )
    with pytest.raises(IdentityStateError):
        serialize_repository_identity_state(missing)
    with pytest.raises(IdentityStateError):
        serialize_repository_identity_state(blocked)


def test_signal_vocabulary_is_stable_and_bounded():
    assert set(MAJOR_CHANGE_SIGNAL_IDS) == {
        "entrypoint_family_changed",
        "primary_interface_changed",
        "high_deleted_file_ratio",
        "high_added_file_ratio",
        "framework_manifest_changed",
        "dominant_structure_changed",
        "runtime_environment_changed",
        "manual_operator_flag",
    }
