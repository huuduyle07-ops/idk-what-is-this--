from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from core import index_execution, index_manifest
from core.index_delta_shadow import (
    STATUS_COLD_BUILD,
    STATUS_IDENTITY_BLOCKED,
    STATUS_MANIFEST_INVALID,
    STATUS_OBSERVED_MANIFEST_FAILED,
    STATUS_PLANNER_UNAVAILABLE,
    STATUS_READY,
    STATUS_SHADOW_DISABLED,
    attach_production_diagnostics,
    build_index_delta_shadow,
)
from core.repository_identity import (
    build_code_index_scope,
    derive_repository_id,
)
from core.repository_identity_state import (
    CanonicalIdentityPermissions,
    DECISION_SAME_PROJECT,
    IDENTITY_STATUS_ARCHIVED,
    IDENTITY_STATUS_BLOCKED,
    SIGNAL_ENTRYPOINT_FAMILY_CHANGED,
    SIGNAL_PRIMARY_INTERFACE_CHANGED,
    apply_human_identity_decision,
    apply_major_change_candidate,
    classify_major_change_candidate,
    initialize_repository_identity_state,
)
from core.repository_inventory import create_repository_inventory
import scripts.create_index_delta_shadow_audit as audit_script


CONFIRMED_AT = "2026-07-29T00:00:00+00:00"


def _write_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "alpha.py").write_text("alpha = 1\n", encoding="utf-8")
    (repo / "beta.py").write_text("beta = 2\n", encoding="utf-8")
    (repo / ".gitignore").write_text("", encoding="utf-8")
    (repo / "diagram.bin").write_bytes(b"not source")
    (repo / "session_log.txt").write_text(
        "control metadata\n",
        encoding="utf-8",
    )
    return repo


def _confirmed(repo: Path):
    result = apply_human_identity_decision(
        initialize_repository_identity_state(repo),
        DECISION_SAME_PROJECT,
        confirmed_at=CONFIRMED_AT,
        confirmed_by="human",
        reason="Confirmed for INDEX.1E.1 shadow tests.",
        confirmed_project_tag="shadow-fixture",
    )
    assert result.valid, result.errors
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
        detected_at="2026-07-29T00:01:00+00:00",
        evidence=["Entrypoint and interface changed."],
    )
    assert result.valid, result.errors
    return result.state


@pytest.fixture
def isolated_manifest_root(tmp_path, monkeypatch):
    root = tmp_path / "agent"
    monkeypatch.setattr(index_manifest, "AGENT_DIR", root)
    return root


def _binding(repo: Path) -> dict:
    return {
        "repository_id": derive_repository_id(repo),
        "architecture_epoch": None,
        "index_scope": build_code_index_scope(repo),
    }


def _seed_applied(repo: Path, inventory):
    manifest, delta = index_manifest.inspect_repository_delta(
        str(repo),
        inventory=inventory,
        indexable_only=True,
        embedding_signature=(
            index_manifest.build_current_index_embedding_signature()
        ),
        **_binding(repo),
    )
    index_manifest.save_repository_manifest(str(repo), manifest)
    return manifest, delta


def _seed_applied_with_embedding_signature(
    repo: Path,
    inventory,
    embedding_signature,
):
    manifest, delta = index_manifest.inspect_repository_delta(
        str(repo),
        inventory=inventory,
        indexable_only=True,
        embedding_signature=embedding_signature,
        **_binding(repo),
    )
    index_manifest.save_repository_manifest(str(repo), manifest)
    return manifest, delta


def _build(
    repo: Path,
    *,
    inventory=None,
    identity_state=None,
    persistence_enabled=True,
    database_available=True,
    embedding_enabled=False,
    embedding_compatibility_evidence=None,
):
    return build_index_delta_shadow(
        str(repo),
        inventory=inventory or create_repository_inventory(repo),
        identity_state=(
            identity_state
            if identity_state is not None
            else _confirmed(repo)
        ),
        production_index_scope=build_code_index_scope(repo),
        persistence_enabled=persistence_enabled,
        database_available=database_available,
        embedding_enabled=embedding_enabled,
        embedding_compatibility_evidence=(
            embedding_compatibility_evidence
        ),
    )


def test_run_a_cold_is_all_added_and_never_authoritative(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    shadow = _build(repo, inventory=inventory)

    assert shadow["status"] == STATUS_COLD_BUILD
    assert shadow["authoritative"] is False
    assert shadow["manifest"] == {
        "load_status": "missing",
        "load_reason": "manifest_missing",
        "previous_applied_present": False,
        "artifact_present": False,
        "legacy_binding": False,
        "observed_built": True,
        "policy_changed": False,
        "previous_records_excluded": 0,
        "embedding_signature_status": "production_embedding_disabled",
        "baseline_kind": "cold_build",
    }
    assert shadow["delta"]["added"] == ["alpha.py", "beta.py"]
    assert shadow["delta"]["counts"] == {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "unchanged": 0,
    }
    assert shadow["membership"] == {
        "repository_members": 5,
        "indexable_members": 2,
        "manifest_control_files": 1,
        "non_indexable_retained_metadata": 2,
    }
    assert shadow["plan"]["parse_files"] == ["alpha.py", "beta.py"]
    assert shadow["plan"]["replacement_files"] == [
        "alpha.py",
        "beta.py",
    ]
    execution = shadow["production_execution"]
    assert execution["plan_controls_execution"] is False
    assert execution["manifest_saved"] is False
    assert execution["manifest_advance_allowed"] is False
    assert not index_manifest.get_repository_manifest_path(repo).exists()


def test_run_b_unchanged_reuses_hashes_and_recommends_no_changed_work(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    _seed_applied(repo, inventory)
    path = index_manifest.get_repository_manifest_path(repo)
    before = path.read_bytes()

    shadow = _build(repo, inventory=inventory)

    assert shadow["status"] == STATUS_READY
    assert shadow["manifest"]["load_status"] == "loaded"
    assert shadow["delta"]["unchanged"] == ["alpha.py", "beta.py"]
    assert shadow["plan"]["changed_file_actions"] == 0
    assert shadow["plan"]["deleted_file_actions"] == 0
    assert shadow["plan"]["unchanged_noop_recommendations"] == 2
    assert shadow["observed_manifest"]["fingerprints_reused"] == 2
    assert shadow["observed_manifest"]["fingerprints_computed"] == 0
    assert path.read_bytes() == before


def test_run_c_and_mtime_only_content_rules_are_deterministic(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    first_inventory = create_repository_inventory(repo)
    _seed_applied(repo, first_inventory)

    alpha = repo / "alpha.py"
    stat_before = alpha.stat()
    os.utime(
        alpha,
        ns=(
            stat_before.st_atime_ns,
            stat_before.st_mtime_ns + 1_000_000,
        ),
    )
    unchanged = _build(
        repo,
        inventory=create_repository_inventory(repo),
    )
    assert unchanged["delta"]["modified"] == []
    assert unchanged["delta"]["unchanged"] == [
        "alpha.py",
        "beta.py",
    ]
    assert (
        unchanged["observed_manifest"]["fingerprints_computed"]
        == 1
    )

    (repo / "beta.py").write_text("beta = 3\n", encoding="utf-8")
    modified = _build(
        repo,
        inventory=create_repository_inventory(repo),
    )
    assert modified["delta"]["modified"] == ["beta.py"]
    assert modified["delta"]["unchanged"] == ["alpha.py"]
    assert modified["plan"]["parse_files"] == ["beta.py"]
    assert modified["plan"]["replacement_files"] == ["beta.py"]


def test_run_d_deleted_and_newly_ignored_are_cleanup_recommendations(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    (repo / "generated.py").write_text("x = 1\n", encoding="utf-8")
    first_inventory = create_repository_inventory(repo)
    _seed_applied(repo, first_inventory)

    (repo / "beta.py").unlink()
    deleted = _build(
        repo,
        inventory=create_repository_inventory(repo),
    )
    assert deleted["delta"]["deleted"] == ["beta.py"]
    assert deleted["plan"]["deleted_files"] == ["beta.py"]

    (repo / ".cattusignore").write_text(
        "generated.py\n",
        encoding="utf-8",
    )
    ignored = _build(
        repo,
        inventory=create_repository_inventory(repo),
    )
    assert ignored["delta"]["deleted"] == [
        "beta.py",
        "generated.py",
    ]
    assert ignored["manifest"]["policy_changed"] is True
    assert ignored["plan"]["policy_changed"] is True
    assert ignored["plan"]["force_full_reindex"] is True


def test_invalid_manifest_is_not_cold_or_destructive_and_is_immutable(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    path = index_manifest.get_repository_manifest_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")
    before = path.read_bytes()

    shadow = _build(repo, inventory=inventory)

    assert shadow["status"] == STATUS_MANIFEST_INVALID
    assert shadow["manifest"]["load_status"] == "invalid"
    assert shadow["manifest"]["baseline_kind"] is None
    assert shadow["manifest"]["observed_built"] is True
    assert shadow["delta"]["available"] is False
    assert shadow["plan"]["status"] == STATUS_PLANNER_UNAVAILABLE
    assert shadow["plan"]["deleted_files"] == []
    assert path.read_bytes() == before


def test_identity_permissions_are_future_candidates_only(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)

    confirmed = _build(
        repo,
        inventory=inventory,
        identity_state=_confirmed(repo),
    )
    assert confirmed["identity_status"] == "confirmed"
    assert confirmed["identity"]["future_execution_allowed"] is True
    assert confirmed["plan"]["future_executable_candidate"] is True
    assert confirmed["authoritative"] is False

    initial = _build(
        repo,
        inventory=inventory,
        identity_state=initialize_repository_identity_state(repo),
    )
    assert initial["plan"]["status"] == STATUS_IDENTITY_BLOCKED
    assert initial["identity"]["future_execution_allowed"] is False
    assert initial["plan"]["parse_files"] == ["alpha.py", "beta.py"]

    major = _build(
        repo,
        inventory=inventory,
        identity_state=_major_pending(repo),
    )
    assert major["plan"]["status"] == STATUS_IDENTITY_BLOCKED
    assert major["identity"]["future_deletion_allowed"] is False

    forged = replace(
        initialize_repository_identity_state(repo),
        identity_status=IDENTITY_STATUS_BLOCKED,
        state_errors=("blocked fixture",),
    )
    blocked = _build(
        repo,
        inventory=inventory,
        identity_state=forged,
    )
    assert blocked["identity_status"] == IDENTITY_STATUS_BLOCKED
    assert blocked["identity"]["future_execution_allowed"] is False


def test_persistence_disabled_still_observes_but_cannot_claim_authority(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    shadow = _build(
        repo,
        persistence_enabled=False,
        database_available=False,
    )

    assert shadow["manifest"]["observed_built"] is True
    assert shadow["delta"]["counts"]["added"] == 2
    assert shadow["plan"]["status"] == "ready_with_warnings"
    assert shadow["plan"]["parse_actions"] == 2
    assert shadow["plan"]["replacement_actions"] == 0
    assert shadow["production_execution"]["persistence_enabled"] is False
    assert (
        shadow["production_execution"]["manifest_advance_allowed"]
        is False
    )
    assert shadow["authoritative"] is False


def test_existing_classifier_and_planner_are_called_once(
    tmp_path,
    isolated_manifest_root,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    calls = {"delta": 0, "plan": 0}
    real_delta = index_manifest.inspect_repository_delta
    real_plan = index_execution.build_index_execution_plan

    def counting_delta(*args, **kwargs):
        calls["delta"] += 1
        return real_delta(*args, **kwargs)

    def counting_plan(*args, **kwargs):
        calls["plan"] += 1
        return real_plan(*args, **kwargs)

    monkeypatch.setattr(
        index_manifest,
        "inspect_repository_delta",
        counting_delta,
    )
    monkeypatch.setattr(
        index_execution,
        "build_index_execution_plan",
        counting_plan,
    )

    shadow = _build(repo)

    assert shadow["delta"]["available"] is True
    assert calls == {"delta": 1, "plan": 1}


def test_planner_failure_preserves_manifest_and_delta_observation(
    tmp_path,
    isolated_manifest_root,
    monkeypatch,
):
    repo = _write_repo(tmp_path)

    def fail_planner(*_args, **_kwargs):
        raise RuntimeError("planner fixture unavailable")

    monkeypatch.setattr(
        index_execution,
        "build_index_execution_plan",
        fail_planner,
    )

    shadow = _build(repo)

    assert shadow["status"] == STATUS_PLANNER_UNAVAILABLE
    assert shadow["manifest"]["load_status"] == "missing"
    assert shadow["manifest"]["load_reason"] == "manifest_missing"
    assert shadow["manifest"]["observed_built"] is True
    assert shadow["delta"]["available"] is True
    assert shadow["delta"]["added"] == ["alpha.py", "beta.py"]
    assert shadow["plan"]["status"] == STATUS_PLANNER_UNAVAILABLE
    assert shadow["plan"]["blocked_reason"] == "planner_failed"
    assert shadow["plan"]["error_category"] == "planner_failed"
    assert shadow["plan"]["future_executable_candidate"] is False
    assert "planner_unavailable" in shadow["warnings"]
    assert shadow["authoritative"] is False


_CURRENT_EMBEDDING_SIGNATURE = index_manifest.EmbeddingSignature(
    provider_id="fixture-provider",
    model="fixture-model-v2",
    dimension=384,
)


@pytest.mark.parametrize(
    (
        "previous_signature",
        "expected_compatibility",
        "expected_warning",
    ),
    (
        pytest.param(
            _CURRENT_EMBEDDING_SIGNATURE,
            "compatible",
            None,
            id="matching-signature",
        ),
        pytest.param(
            None,
            "unknown",
            "embedding_signature_not_persisted",
            id="legacy-manifest-without-signature",
        ),
        pytest.param(
            index_manifest.EmbeddingSignature(
                provider_id="fixture-provider",
                model="fixture-model-v1",
                dimension=384,
            ),
            "same_dimension_drift",
            "embedding_signature_drift",
            id="same-dimension-drift",
        ),
        pytest.param(
            index_manifest.EmbeddingSignature(
                provider_id="fixture-provider",
                model="fixture-model-v1",
                dimension=768,
            ),
            "incompatible_dimension",
            "embedding_dimension_incompatible",
            id="dimension-mismatch",
        ),
    ),
)
def test_applied_manifest_signature_drives_embedding_compatibility(
    tmp_path,
    isolated_manifest_root,
    monkeypatch,
    previous_signature,
    expected_compatibility,
    expected_warning,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    _seed_applied_with_embedding_signature(
        repo,
        inventory,
        previous_signature,
    )
    monkeypatch.setattr(
        index_manifest,
        "build_current_index_embedding_signature",
        lambda: _CURRENT_EMBEDDING_SIGNATURE,
    )

    shadow = _build(
        repo,
        inventory=inventory,
        embedding_enabled=True,
    )

    assert shadow["manifest"]["load_status"] == "loaded"
    assert shadow["plan"]["embedding_compatibility"] == (
        expected_compatibility
    )
    assert shadow["plan"]["embedding_compatibility_source"] == (
        "applied_manifest_signature"
        if previous_signature is not None
        else "applied_signature_unavailable"
    )
    assert shadow["authoritative"] is False
    if expected_warning is None:
        assert not {
            "embedding_signature_not_persisted",
            "embedding_signature_drift",
            "embedding_dimension_incompatible",
        }.intersection(shadow["warnings"])
    else:
        assert expected_warning in shadow["warnings"]

    if expected_compatibility == "same_dimension_drift":
        assert shadow["plan"]["full_reembed_required"] is True
        assert shadow["plan"]["embedding_files"] == [
            "alpha.py",
            "beta.py",
        ]
    elif expected_compatibility == "incompatible_dimension":
        assert shadow["plan"]["blocked_reason"] == (
            "embedding_dimension_incompatible"
        )
        assert shadow["plan"]["future_executable_candidate"] is False


def test_embedding_compatibility_cold_off_and_current_unavailable(
    tmp_path,
    isolated_manifest_root,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    monkeypatch.setattr(
        index_manifest,
        "build_current_index_embedding_signature",
        lambda: _CURRENT_EMBEDDING_SIGNATURE,
    )

    cold = _build(
        repo,
        inventory=inventory,
        embedding_enabled=True,
    )
    assert cold["manifest"]["load_status"] == "missing"
    assert cold["plan"]["embedding_compatibility"] == "compatible"
    assert cold["plan"]["embedding_compatibility_source"] == (
        "cold_build_no_existing_vectors"
    )
    assert cold["plan"]["embedding_files"] == ["alpha.py", "beta.py"]

    _seed_applied_with_embedding_signature(
        repo,
        inventory,
        _CURRENT_EMBEDDING_SIGNATURE,
    )
    off = _build(
        repo,
        inventory=inventory,
        embedding_enabled=False,
    )
    assert off["plan"]["embedding_compatibility"] == "off"
    assert off["plan"]["embedding_compatibility_source"] == (
        "production_embedding_disabled"
    )
    assert off["plan"]["embedding_action"] == "disabled"
    assert off["plan"]["embedding_files"] == []

    monkeypatch.setattr(
        index_manifest,
        "build_current_index_embedding_signature",
        lambda: None,
    )
    unavailable = _build(
        repo,
        inventory=inventory,
        embedding_enabled=True,
    )
    assert unavailable["plan"]["embedding_compatibility"] == "unknown"
    assert unavailable["plan"]["embedding_compatibility_source"] == (
        "applied_signature_unavailable"
    )
    assert (
        "current_embedding_signature_unverified"
        in unavailable["warnings"]
    )
    assert unavailable["plan"]["future_executable_candidate"] is False


def test_invalid_applied_embedding_signature_fails_closed_and_is_immutable(
    tmp_path,
    isolated_manifest_root,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    _seed_applied_with_embedding_signature(
        repo,
        inventory,
        _CURRENT_EMBEDDING_SIGNATURE,
    )
    path = index_manifest.get_repository_manifest_path(repo)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["embedding_signature"]["dimension"] = 0
    path.write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )
    before = path.read_bytes()
    monkeypatch.setattr(
        index_manifest,
        "build_current_index_embedding_signature",
        lambda: _CURRENT_EMBEDDING_SIGNATURE,
    )

    shadow = _build(
        repo,
        inventory=inventory,
        embedding_enabled=True,
    )

    assert shadow["status"] == STATUS_MANIFEST_INVALID
    assert shadow["manifest"]["load_status"] == "invalid"
    assert shadow["manifest"]["load_reason"] == "manifest_payload_invalid"
    assert shadow["delta"]["available"] is False
    assert shadow["plan"]["future_executable_candidate"] is False
    assert path.read_bytes() == before


def test_dimension_compatibility_drives_descriptive_reembedding_only(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    _seed_applied(repo, inventory)
    shadow = _build(
        repo,
        inventory=inventory,
        embedding_enabled=True,
        embedding_compatibility_evidence=(
            index_execution.EmbeddingCompatibility
            .SAME_DIMENSION_DRIFT
        ),
    )

    assert shadow["plan"]["embedding_compatibility"] == (
        "same_dimension_drift"
    )
    assert shadow["plan"]["full_reembed_required"] is True
    assert shadow["plan"]["parse_files"] == []
    assert shadow["plan"]["embedding_files"] == [
        "alpha.py",
        "beta.py",
    ]
    assert shadow["plan"]["replacement_files"] == [
        "alpha.py",
        "beta.py",
    ]
    assert shadow["production_execution"]["plan_controls_execution"] is False


def test_shadow_errors_are_sanitized_and_do_not_expose_absolute_roots(
    tmp_path,
    isolated_manifest_root,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    database_url = (
        "postgresql://shadow-user:shadow-password@"
        "db.example.test/cattus?token=shadow-token"
    )

    def fail_observation(*_args, **_kwargs):
        raise RuntimeError(f"{repo}: {database_url}")

    monkeypatch.setattr(
        index_manifest,
        "inspect_repository_delta",
        fail_observation,
    )
    shadow = _build(repo)
    rendered = json.dumps(shadow, sort_keys=True)

    assert shadow["status"] == STATUS_OBSERVED_MANIFEST_FAILED
    assert shadow["manifest"]["load_status"] == "missing"
    assert shadow["manifest"]["load_reason"] == "manifest_missing"
    assert shadow["manifest"]["observed_built"] is False
    assert shadow["observed_manifest"]["status"] == "failed"
    assert shadow["observed_manifest"]["invalid_entries"] == 1
    assert shadow["observed_manifest"]["error_category"] == (
        "observed_manifest_build_failed"
    )
    assert shadow["observed_manifest"]["error_message"]
    assert shadow["plan"]["blocked_reason"] == "observed_manifest_failed"
    assert str(repo) not in rendered
    assert database_url not in rendered
    assert "shadow-user" not in rendered
    assert "shadow-password" not in rendered
    assert "shadow-token" not in rendered


def test_archived_unsupplied_and_project_tag_none_have_no_future_authority(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    no_permissions = CanonicalIdentityPermissions(
        canonical_build_allowed=False,
        canonical_refresh_allowed=False,
        reconciliation_allowed=False,
        applied_manifest_advance_allowed=False,
        trusted_current_claim_allowed=False,
    )
    archived_state = replace(
        _confirmed(repo),
        identity_status=IDENTITY_STATUS_ARCHIVED,
        permissions=no_permissions,
    )
    project_tag_none_state = initialize_repository_identity_state(repo)
    assert project_tag_none_state.project_tag is None

    archived = _build(
        repo,
        inventory=inventory,
        identity_state=archived_state,
    )
    project_tag_none = _build(
        repo,
        inventory=inventory,
        identity_state=project_tag_none_state,
    )
    unsupplied = build_index_delta_shadow(
        str(repo),
        inventory=inventory,
        identity_state=None,
        production_index_scope=build_code_index_scope(repo),
        persistence_enabled=True,
        database_available=True,
        embedding_enabled=False,
    )

    assert archived["identity_status"] == IDENTITY_STATUS_ARCHIVED
    assert unsupplied["identity"]["source"] in {
        "persistent_missing",
        "persistent_loaded",
    }
    for shadow in (archived, project_tag_none, unsupplied):
        assert shadow["identity"]["future_execution_allowed"] is False
        assert shadow["identity"]["future_deletion_allowed"] is False
        assert shadow["plan"]["future_executable_candidate"] is False
        assert shadow["authoritative"] is False


def test_production_scope_mismatch_has_no_future_authority(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    shadow = build_index_delta_shadow(
        str(repo),
        inventory=create_repository_inventory(repo),
        identity_state=_confirmed(repo),
        production_index_scope=build_code_index_scope(
            repo,
            architecture_epoch=1,
        ),
        persistence_enabled=True,
        database_available=True,
        embedding_enabled=False,
    )

    assert (
        shadow["identity"]["production_scope_matches_identity"]
        is False
    )
    assert shadow["identity"]["future_execution_allowed"] is False
    assert shadow["identity"]["future_deletion_allowed"] is False
    assert shadow["plan"]["future_executable_candidate"] is False
    assert "production_index_scope_mismatch" in shadow["warnings"]
    assert shadow["authoritative"] is False


def test_production_scope_mismatch_disables_shadow_comparison(
    tmp_path,
    isolated_manifest_root,
):
    repo = _write_repo(tmp_path)
    shadow = build_index_delta_shadow(
        str(repo),
        inventory=create_repository_inventory(repo),
        identity_state=_confirmed(repo),
        production_index_scope=build_code_index_scope(
            repo,
            architecture_epoch=1,
        ),
        persistence_enabled=True,
        database_available=True,
        embedding_enabled=False,
    )
    assert (
        shadow["identity"]["production_scope_matches_identity"]
        is False
    )

    attached = attach_production_diagnostics(
        shadow,
        file_outcomes=(),
        reconciliation={
            "performed": False,
            "dependencies_deleted": 0,
            "code_units_deleted": 0,
            "skipped_reason": "scope_mismatch_fixture",
        },
        database_available=True,
    )

    comparison = attached["production_execution"]["comparison"]
    assert comparison["available"] is False
    assert comparison["unavailable_reason"] == (
        "production_scope_mismatch"
    )
    assert comparison["matches_shadow_recommendation"] is None
    assert comparison["shadow_plan_remains_valid"] is None


def test_shadow_can_be_disabled_without_manifest_or_plan_authority(
    tmp_path,
    isolated_manifest_root,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    monkeypatch.setenv("INDEX_DELTA_SHADOW_ENABLED", "0")

    shadow = _build(repo)

    assert shadow["status"] == STATUS_SHADOW_DISABLED
    assert shadow["manifest"]["load_reason"] == "manifest_not_inspected"
    assert shadow["manifest"]["observed_built"] is False
    assert shadow["delta"]["available"] is False
    assert shadow["plan"]["blocked_reason"] == "shadow_disabled"
    assert shadow["plan"]["future_executable_candidate"] is False
    assert shadow["authoritative"] is False
    assert not index_manifest.get_repository_manifest_path(repo).exists()


def test_shadow_module_has_no_walk_write_or_execution_dispatch():
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "index_delta_shadow.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "os.walk(",
        ".rglob(",
        'glob("**/*")',
        "replace_code_index_for_file",
        "reconcile_code_index_scope",
        "delete_code_index_for_file",
        "save_repository_manifest(",
        "ActivationGraph",
        "requests",
        "httpx",
        "socket",
        "threading",
        "multiprocessing",
    ):
        assert forbidden not in source


def test_audit_json_and_markdown_generation_is_deterministic(tmp_path):
    validation = {
        "focused_tests": "passed",
        "new_failures": 0,
        "repository_wide_observed": {
            "passed": 6360,
            "skipped": 5,
            "failed": 48,
        },
    }
    first_report = audit_script.build_report(
        validation=validation,
    )
    second_report = audit_script.build_report(
        validation=validation,
    )

    assert first_report == second_report
    assert (
        audit_script.render_markdown(first_report)
        == audit_script.render_markdown(second_report)
    )
    first_paths = audit_script.write_report(
        first_report,
        repo_root=tmp_path,
    )
    first_bytes = {
        name: Path(path).read_bytes()
        for name, path in first_paths.items()
    }
    second_paths = audit_script.write_report(
        second_report,
        repo_root=tmp_path,
    )
    second_bytes = {
        name: Path(path).read_bytes()
        for name, path in second_paths.items()
    }

    assert first_paths == second_paths
    assert first_bytes == second_bytes
    json_payload = json.loads(
        Path(first_paths["agent_json"]).read_text(encoding="utf-8")
    )
    assert json_payload["status"] == (
        "INDEX_1E_1_COMPLETE_WITH_WARNINGS"
    )
