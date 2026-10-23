"""Live shared-authority gate regressions; no Java or container effects."""
import copy
from dataclasses import replace
import json
from unittest.mock import patch

import pytest

from core import behavioral_diagnostic_executor_retry as retry
from core.runtime.synthetic import synthetic_read_only_reflection as reflection
from core.runtime.synthetic import synthetic_reflection_execution_admission as admission
from core.runtime.synthetic import synthetic_runtime_authorization as authorization
from tests._preflight_runtime1_guard import no_runtime_effects


@pytest.fixture(autouse=True)
def effects():
    with no_runtime_effects(strict=True) as evidence:
        with patch("threading.Thread.start", side_effect=evidence.deny("threading.Thread.start")):
            yield evidence
    assert evidence.denied_attempts == {}


@pytest.fixture
def safe_patch(effects):
    # Restore overrides before the enclosing guard restores its own patches.
    with pytest.MonkeyPatch.context() as monkeypatch:
        yield monkeypatch


def live_pair():
    spec = authorization.executor1r_decrement_3_spec()
    auth = authorization.issue_synthetic_runtime_authorization(spec,
        source=authorization.get_executor1r_decrement_3_source())
    before, after = reflection.executor1r_before_request(), reflection.executor1r_after_request()
    return [auth, before, after,
        admission.issue_synthetic_reflection_execution_admission(auth, before),
        admission.issue_synthetic_reflection_execution_admission(auth, after)]


def test_retry_uses_one_live_authorization_for_both_roles_and_stops_at_lifecycle(safe_patch):
    issued, admitted = [], []
    original_issue = authorization.issue_synthetic_runtime_authorization
    original_admit = admission.issue_synthetic_reflection_execution_admission

    def issue(*args, **kwargs):
        auth = original_issue(*args, **kwargs)
        issued.append(auth)
        return auth

    def admit(auth, request):
        grant = original_admit(auth, request)
        admitted.append((auth, request, grant))
        return grant

    safe_patch.setattr(authorization, "issue_synthetic_runtime_authorization", issue)
    safe_patch.setattr(admission, "issue_synthetic_reflection_execution_admission", admit)
    report = retry.verify()
    assert report["status"] == retry.BLOCKED_AUTH_LIFECYCLE
    assert len(issued) == 1 and len(admitted) == 2
    auth = issued[0]
    assert all(item[0] is auth for item in admitted)
    assert report["synthetic_runtime_authorizations_issued"] == 1
    assert report["exactly_one_scenario_authorization_used"] is True
    assert report["shared_authorization_coherence"] is True
    assert report["scenario_authorization"]["issuance_id"] == auth.issuance_id
    assert report["before_admission"]["synthetic_authorization_issuance_id"] == auth.issuance_id
    assert report["after_admission"]["synthetic_authorization_issuance_id"] == auth.issuance_id
    assert report["before_request"]["issuance_id"] != report["after_request"]["issuance_id"]
    for _, request, grant in admitted:
        assert admission.synthetic_reflection_admission_satisfies_executor(grant, auth, request)
        assert grant.consumption_state == "issued"
    assert authorization.validate_synthetic_runtime_authorization(auth,
        spec=authorization.executor1r_decrement_3_spec(),
        source=authorization.get_executor1r_decrement_3_source()) is auth
    assert auth.synthetic_runtime_authorizations_consumed == 0


def test_lifecycle_block_preserves_unmeasured_facts_and_zero_effects():
    report = retry.verify()
    for key in ("synthetic_runtime_authorizations_consumed", "real_runtime_authorizations_consumed",
            "before_reflection_admissions_consumed", "after_reflection_admissions_consumed",
            "reflection_execution_count", "public_method_invocation_count",
            "synthetic_behavioral_execution_count", "bank_execution_count",
            "real_behavioral_execution_count", "compile_count", "jvm_execution_count",
            "console_count", "network_calls", "repository_writes", "apply_actions",
            "model_calls", "author_calls", "controller_thread_start_attempts",
            "phase_containers_created", "host_java_artifacts_created"):
        assert report[key] == 0
    for key in ("measured_observations", "measured_before", "measured_direct_return",
            "measured_after", "fixture_expectation_comparison", "harness_sha256",
            "class_manifest", "compile_stage", "runtime_stage", "positive_runtime_receipt",
            "positive_runtime_receipt_fingerprint", "remaining_phase_containers"):
        assert report[key] is None
    assert report["fixture_expectations"] == {"before": 10, "return": True, "after": 7}
    assert report["runtime_authorization_state"] == authorization.ISSUED
    assert report["before_admission_consumption_state"] == "issued"
    assert report["after_admission_consumption_state"] == "issued"
    assert report["source_projected"] is False
    assert report["positive_runtime_receipt_issued"] is False
    assert report["reflection_consumption_implemented"] is False
    assert report["cleanup_outcome"] == "not_required_no_runtime_resources_created"
    assert report["sandbox2_authentication"] == "not_attempted_pre_execution_gate"
    assert report["java1_authentication"] == "not_attempted_pre_execution_gate"
    assert report["java_compatibility"] == "not_evaluated_pre_execution_gate"


def test_gate_calls_all_issuing_owners_public_validators(safe_patch):
    calls = {}
    for owner, name in (
            (authorization, "validate_synthetic_runtime_authorization"),
            (reflection, "validate_synthetic_reflection_request"),
            (admission, "validate_synthetic_reflection_execution_admission")):
        original = getattr(owner, name)

        def record(*args, _original=original, _name=name, **kwargs):
            calls[_name] = calls.get(_name, 0) + 1
            return _original(*args, **kwargs)

        safe_patch.setattr(owner, name, record)
    assert retry.verify()["status"] == retry.BLOCKED_AUTH_LIFECYCLE
    assert len(calls) == 3 and all(value > 0 for value in calls.values())


@pytest.mark.parametrize("index", range(5))
@pytest.mark.parametrize("clone", (copy.copy, replace, lambda value: value.as_dict()))
def test_gate_rejects_copies_reconstruction_and_reports(index, clone):
    pair = live_pair()
    pair[index] = clone(pair[index])
    with pytest.raises(retry.ExecutorRetryGateError) as error:
        retry.validate_shared_authorization(*pair)
    assert error.value.code == retry.BLOCKED_AUTH_COHERENCE


def test_gate_rejects_admissions_from_two_different_live_authorizations():
    pair = live_pair()
    foreign = live_pair()
    pair[2], pair[4] = foreign[2], foreign[4]
    with pytest.raises(retry.ExecutorRetryGateError):
        retry.validate_shared_authorization(*pair)


@pytest.mark.parametrize("swap", ("requests", "admissions", "both", "reuse_before"))
def test_gate_rejects_swapped_roles_and_reuse(swap):
    pair = live_pair()
    if swap in ("requests", "both"):
        pair[1], pair[2] = pair[2], pair[1]
    if swap in ("admissions", "both"):
        pair[3], pair[4] = pair[4], pair[3]
    if swap == "reuse_before":
        pair[2], pair[4] = pair[1], pair[3]
    with pytest.raises(retry.ExecutorRetryGateError):
        retry.validate_shared_authorization(*pair)


def test_after_issuance_failure_stops_without_issuing_another_authorization(safe_patch):
    calls = []
    original_issue = admission.issue_synthetic_reflection_execution_admission

    def fail_after(auth, request):
        calls.append(auth)
        if request.observation_role == reflection.AFTER_ROLE:
            raise ValueError("after admission unavailable")
        return original_issue(auth, request)

    safe_patch.setattr(admission, "issue_synthetic_reflection_execution_admission", fail_after)
    report = retry.verify()
    assert report["status"] == retry.BLOCKED_AUTH_COHERENCE
    assert len(calls) == 2 and calls[0] is calls[1]
    assert report["synthetic_runtime_authorizations_issued"] == 1
    assert report["before_admission_consumption_state"] == "issued"
    assert report["after_admission"] is None
    assert report["synthetic_runtime_authorizations_consumed"] == 0


def test_unauthenticated_scenario_handle_cannot_reach_admission(safe_patch):
    original = authorization.issue_synthetic_runtime_authorization

    def copied(*args, **kwargs):
        return copy.copy(original(*args, **kwargs))

    def forbidden(*args, **kwargs):
        raise AssertionError("admission reached before authorization authentication")

    safe_patch.setattr(authorization, "issue_synthetic_runtime_authorization", copied)
    safe_patch.setattr(admission, "issue_synthetic_reflection_execution_admission", forbidden)
    report = retry.verify()
    assert report["status"] == retry.BLOCKED_UNRESOLVED
    assert report["error_code"] == "synthetic_authorization_unauthenticated"
    assert report["before_admission"] is None


def test_exported_report_cannot_recreate_live_gate_inputs():
    report = json.loads(json.dumps(retry.verify()))
    assert report["report_only"] is True
    assert "_signature" not in json.dumps(report)
    with pytest.raises(retry.ExecutorRetryGateError):
        retry.validate_shared_authorization(report["scenario_authorization"],
            report["before_request"], report["after_request"],
            report["before_admission"], report["after_admission"])


def test_replay_is_effect_free_and_never_labels_expectations_as_measurements():
    from scripts.replay_patch_candidate_behavior_executor1r_retry import replay
    report = replay()
    assert report["status"] == retry.BLOCKED_AUTH_LIFECYCLE
    assert report["effect_denial"] == {"strict": True, "denied_attempts": {},
        "controller_thread_start_attempts": 0}
    assert report["measured_observations"] is None
