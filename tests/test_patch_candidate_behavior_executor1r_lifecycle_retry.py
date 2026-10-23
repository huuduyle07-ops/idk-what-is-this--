"""Pure operational stop-gate tests; no infrastructure or behavioral execution."""
import copy
from dataclasses import fields, replace
import json
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import behavioral_diagnostic_executor_lifecycle_retry as owner


@pytest.fixture(autouse=True)
def effects():
    with no_runtime_effects(strict=True) as evidence:
        with patch("threading.Thread.start", side_effect=evidence.deny("threading.Thread.start")):
            yield evidence
    assert evidence.denied_attempts == {}


@pytest.fixture
def safe_patch(effects):
    with pytest.MonkeyPatch.context() as monkeypatch:
        yield monkeypatch


def graph():
    auth = owner.authorization.issue_synthetic_runtime_authorization(
        owner.authorization.executor1r_decrement_3_spec(),
        source=owner.authorization.get_executor1r_decrement_3_source())
    runtime = owner.runtime.issue_synthetic_runtime_execution_lease(auth)
    handles = {"authorization": auth, "runtime_lease": runtime}
    for label, role, factory in (("before", owner.reflection.BEFORE_ROLE, owner.reflection.executor1r_before_request),
            ("after", owner.reflection.AFTER_ROLE, owner.reflection.executor1r_after_request)):
        request = factory()
        grant = owner.admission.issue_synthetic_reflection_execution_admission(auth, request)
        lease = owner.reflection_lifecycle.issue_synthetic_reflection_execution_lease(
            grant, request, runtime, auth, observation_role=role)
        handles.update({label + "_request": request, label + "_admission": grant, label + "_lease": lease})
    return owner.ExecutorAuthorityGraph(**handles)


def test_one_issued_activation_and_two_subordinate_reads_pass_without_consumption():
    live = graph()
    assert owner.validate_authority_graph(live) is live
    assert live.runtime_lease.lifecycle_state == live.before_lease.lifecycle_state == live.after_lease.lifecycle_state == "ISSUED"
    assert live.before_lease.runtime_execution_lease_id == live.after_lease.runtime_execution_lease_id == live.runtime_lease.lease_id


@pytest.mark.parametrize("field", [f.name for f in fields(owner.ExecutorAuthorityGraph)])
@pytest.mark.parametrize("clone", [copy.copy, replace, lambda value: value.as_dict()])
def test_copied_reconstructed_and_exported_owner_handles_cannot_authenticate(field, clone):
    live = graph()
    changed = replace(live, **{field: clone(getattr(live, field))})
    with pytest.raises(owner.historical.ExecutorRetryGateError):
        owner.validate_authority_graph(changed)


@pytest.mark.parametrize("field", [f.name for f in fields(owner.ExecutorAuthorityGraph)])
def test_foreign_live_upstream_handles_cannot_bind_another_activation(field):
    live, foreign = graph(), graph()
    with pytest.raises(owner.historical.ExecutorRetryGateError):
        owner.validate_authority_graph(replace(live, **{field: getattr(foreign, field)}))


@pytest.mark.parametrize("suffix", ["request", "admission", "lease"])
def test_before_and_after_roles_cannot_be_swapped(suffix):
    live = graph()
    with pytest.raises(owner.historical.ExecutorRetryGateError):
        owner.validate_authority_graph(replace(live, **{
            "before_" + suffix: getattr(live, "after_" + suffix),
            "after_" + suffix: getattr(live, "before_" + suffix)}))


@pytest.mark.parametrize("transition", ["consume", "invalidate"])
def test_terminal_runtime_lease_cannot_reenter_preexecution(transition):
    live = graph()
    getattr(owner.runtime, transition + "_synthetic_runtime_execution_lease")(
        live.runtime_lease, live.authorization)
    with pytest.raises(owner.historical.ExecutorRetryGateError):
        owner.validate_authority_graph(live)


@pytest.mark.parametrize("label,role", [("before", owner.reflection.BEFORE_ROLE), ("after", owner.reflection.AFTER_ROLE)])
def test_invalidated_read_lease_cannot_reenter_preexecution(label, role):
    live = graph()
    owner.reflection_lifecycle.invalidate_synthetic_reflection_execution_lease(
        getattr(live, label + "_lease"), getattr(live, label + "_admission"),
        getattr(live, label + "_request"), live.runtime_lease, live.authorization, observation_role=role)
    with pytest.raises(owner.historical.ExecutorRetryGateError):
        owner.validate_authority_graph(live)


def test_java_contract_audit_checks_exact_schema_and_policy_without_inventing_alias():
    audit = owner.java_profile_contract_audit()
    assert audit["required"] == {"phase_id": "RUNTIME.JAVA.1", "schema_version": "runtime_java_1_v1",
        "seccomp_policy_sha256": "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75"}
    assert audit["java1_receipt_contract"]["seccomp_policy_sha256"] != audit["required"]["seccomp_policy_sha256"]
    assert audit["java1c_receipt_contract"]["schema_version"] == "runtime_java_1c_v1"
    assert audit["compatible_frozen_contract_found"] is False
    assert audit["capabilities_authenticated"] is audit["profile_alias_inferred"] is False


def test_renaming_continuation_module_does_not_change_its_frozen_contract(safe_patch):
    safe_patch.setattr(owner.java1c, "PHASE_ID", "RUNTIME.JAVA.1")
    safe_patch.setattr(owner.java1c, "SCHEMA_VERSION", "runtime_java_1_v1")
    assert owner.java_profile_contract_audit()["compatible_frozen_contract_found"] is False


def test_retry_issues_exactly_one_graph_and_stops_before_all_infrastructure(safe_patch):
    calls = {}
    for module, name in ((owner.authorization, "issue_synthetic_runtime_authorization"),
            (owner.runtime, "issue_synthetic_runtime_execution_lease"),
            (owner.reflection_lifecycle, "issue_synthetic_reflection_execution_lease")):
        original = getattr(module, name)
        def count(*args, _name=name, _original=original, **kwargs):
            calls[_name] = calls.get(_name, 0) + 1
            return _original(*args, **kwargs)
        safe_patch.setattr(module, name, count)
    report = owner.verify()
    assert calls == {"issue_synthetic_runtime_authorization": 1, "issue_synthetic_runtime_execution_lease": 1,
        "issue_synthetic_reflection_execution_lease": 2}
    assert report["status"] == owner.BLOCKED
    assert report["reason"] == "java_profile_contract_mismatch"
    assert report["authority_graph_authenticated"] is report["same_activation_proven"] is True
    for label in ("runtime", "before", "after"):
        assert report[label + "_lease_initial_state"] == report[label + "_lease_final_state"] == "ISSUED"
        assert report[label + "_consumption_point"] is None
    for key in ("compile_count", "jvm_execution_count", "docker_calls", "reflection_execution_count",
            "synthetic_behavioral_execution_count", "public_method_invocation_count", "real_runtime_authorizations_consumed"):
        assert report[key] == 0
    for key in ("measured_before", "measured_direct_return", "measured_after", "positive_runtime_receipt",
            "harness_sha256", "compile_stage", "runtime_stage", "class_manifest", "remaining_phase_containers"):
        assert report[key] is None


def test_after_lease_issuance_failure_does_not_retry_or_consume(safe_patch):
    original = owner.reflection_lifecycle.issue_synthetic_reflection_execution_lease
    def fail_after(*args, **kwargs):
        if kwargs["observation_role"] == owner.reflection.AFTER_ROLE:
            raise ValueError("unavailable AFTER lease")
        return original(*args, **kwargs)
    safe_patch.setattr(owner.reflection_lifecycle, "issue_synthetic_reflection_execution_lease", fail_after)
    report = owner.verify()
    assert report["status"] == owner.BLOCKED
    assert report["synthetic_runtime_authorizations_issued"] == report["runtime_execution_leases_issued"] == 1
    assert report["runtime_lease_final_state"] == report["before_lease_final_state"] == "ISSUED"
    assert report["after_lease_final_state"] is None


def test_changed_contract_cannot_accidentally_enable_an_unimplemented_executor(safe_patch):
    safe_patch.setattr(owner, "java_profile_contract_audit", lambda: {"compatible_frozen_contract_found": True})
    report = owner.verify()
    assert report["status"] == owner.BLOCKED
    assert report["reason"] == "infrastructure_contract_changed_requires_review"
    assert report["runtime_execution_leases_consumed"] == report["docker_calls"] == 0


def test_replay_is_effect_free_exports_no_authority_and_preserves_expectations():
    from scripts.replay_patch_candidate_behavior_executor1r_lifecycle_retry import replay
    report = replay()
    assert report["effect_denial"] == {"strict": True, "denied_attempts": {}, "controller_thread_start_attempts": 0}
    exported = json.loads(json.dumps(report))
    assert exported["fixture_expectations"] == {"before": 10, "return": True, "after": 7}
    assert exported["fixture_expectation_comparison"] is None
    assert exported["positive_runtime_receipt_issued"] is False
    assert "_signature" not in json.dumps(exported)
    with pytest.raises(owner.historical.ExecutorRetryGateError):
        owner.validate_authority_graph(exported)
