from core.index_no_change_fast_path import evaluate_no_change_fast_path
from core.repository_identity_state import (
    DECISION_SAME_PROJECT,
    apply_human_identity_decision,
    initialize_repository_identity_state,
)


def _state(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    result = apply_human_identity_decision(
        initialize_repository_identity_state(repo),
        DECISION_SAME_PROJECT,
        confirmed_at="2026-08-01T00:00:00+00:00",
        confirmed_by="human",
        reason="Confirm stable repository identity for no-change gate tests.",
        confirmed_project_tag="repo",
    )
    assert result.valid, result.errors
    return result.state


def _evidence(state, **overrides):
    shadow = {
        "identity_status": "confirmed",
        "repository_id": state.repository_id,
        "index_scope": state.active_index_scope,
        "architecture_epoch": state.architecture_epoch,
        "identity": {
            "valid": True,
            "future_execution_allowed": True,
            "production_scope_matches_identity": True,
        },
        "delta": {
            "available": True,
            "counts": {
                "added": 0,
                "modified": 0,
                "deleted": 0,
                "unchanged": 1,
            },
        },
    }
    shadow.update(overrides.pop("shadow", {}))
    manifest = {
        "load_status": "loaded",
        "previous_applied_present": True,
        "observed_built": True,
        "previous_records_excluded": 0,
        "policy_changed": False,
        "embedding_signature_status": "applied_manifest_signature",
    }
    manifest.update(overrides.pop("manifest", {}))
    plan = {
        "status": "ready",
        "blocked_reason": "",
        "embedding_compatibility": "compatible",
        "parse_actions": 0,
        "replacement_actions": 0,
        "deleted_file_actions": 0,
    }
    plan.update(overrides.pop("plan", {}))
    return evaluate_no_change_fast_path(
        identity_state=overrides.pop("identity_state", state),
        manifest_load=manifest,
        delta_shadow=shadow,
        execution_plan=plan,
        embedding_runtime=overrides.pop("embedding", {"enabled": True}),
        persistence_mode=overrides.pop(
            "persistence",
            {"enabled": True, "available": True},
        ),
    )


def test_valid_unchanged_state_is_eligible(tmp_path):
    decision = _evidence(_state(tmp_path))
    assert decision.eligible and decision.status == "eligible"


def test_missing_and_invalid_manifests_are_ineligible(tmp_path):
    state = _state(tmp_path)
    assert (
        _evidence(state, manifest={"load_status": "missing"}).status
        == "manifest_missing"
    )
    assert (
        _evidence(state, manifest={"load_status": "invalid"}).status
        == "manifest_invalid"
    )


def test_binding_mismatch_is_ineligible(tmp_path):
    state = _state(tmp_path)
    for status in (
        "root_mismatch",
        "repository_mismatch",
        "scope_mismatch",
        "epoch_mismatch",
    ):
        assert (
            _evidence(state, manifest={"load_status": status}).status
            == "binding_mismatch"
        )


def test_identity_and_persistence_fail_closed(tmp_path):
    state = _state(tmp_path)
    assert _evidence(state, identity_state=None).status == "identity_blocked"
    assert (
        _evidence(
            state,
            persistence={"enabled": False, "available": False},
        ).status
        == "persistence_disabled"
    )


def test_embedding_policy_delta_and_planner_fail_closed(tmp_path):
    state = _state(tmp_path)
    assert (
        _evidence(
            state,
            plan={"embedding_compatibility": "incompatible_dimension"},
        ).status
        == "embedding_incompatible"
    )
    assert _evidence(
        state,
        manifest={"policy_changed": True},
        plan={"policy_changed": True},
    ).status == "policy_changed"
    shadow = {
        "delta": {
            "available": True,
            "counts": {
                "added": 1,
                "modified": 0,
                "deleted": 0,
                "unchanged": 0,
            },
        }
    }
    assert _evidence(state, shadow=shadow).status == "delta_not_empty"
    assert (
        _evidence(state, plan={"status": "planner_unavailable"}).status
        == "planner_unavailable"
    )


def test_contradictory_plan_fails_closed(tmp_path):
    assert (
        _evidence(_state(tmp_path), plan={"parse_actions": 1}).status
        == "invalid_evidence"
    )


def test_legacy_embedding_signature_is_ineligible(tmp_path):
    decision = _evidence(
        _state(tmp_path),
        manifest={
            "embedding_signature_status": "applied_signature_unavailable"
        },
        plan={
            "status": "planner_unavailable",
            "blocked_reason": "embedding_compatibility_unknown",
            "embedding_compatibility": "unknown",
        },
    )
    assert decision.status == "embedding_signature_missing"


def test_embeddings_disabled_uses_off_compatibility(tmp_path):
    decision = _evidence(
        _state(tmp_path),
        embedding={"enabled": False},
        plan={"embedding_compatibility": "off"},
    )
    assert decision.eligible is True


def test_pending_identity_is_blocked(tmp_path):
    repo = tmp_path / "pending"
    repo.mkdir()
    pending = initialize_repository_identity_state(repo)
    decision = _evidence(
        _state(tmp_path),
        identity_state=pending,
    )
    assert decision.status == "identity_blocked"


def test_identity_binding_mismatch_is_blocked(tmp_path):
    state = _state(tmp_path)
    decision = _evidence(
        state,
        shadow={"repository_id": "repository-id-mismatch"},
    )
    assert decision.status == "identity_blocked"


def test_empty_repository_delta_can_be_eligible(tmp_path):
    state = _state(tmp_path)
    decision = _evidence(
        state,
        shadow={
            "delta": {
                "available": True,
                "counts": {
                    "added": 0,
                    "modified": 0,
                    "deleted": 0,
                    "unchanged": 0,
                },
            }
        },
    )
    assert decision.eligible is True


def test_delta_counts_and_paths_cannot_contradict(tmp_path):
    state = _state(tmp_path)
    decision = _evidence(
        state,
        shadow={
            "delta": {
                "available": True,
                "counts": {
                    "added": 0,
                    "modified": 0,
                    "deleted": 0,
                    "unchanged": 1,
                },
                "modified": ["surprise.py"],
            }
        },
    )
    assert decision.status == "invalid_evidence"
