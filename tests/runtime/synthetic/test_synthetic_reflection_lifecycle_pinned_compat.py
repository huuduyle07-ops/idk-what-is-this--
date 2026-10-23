"""PURE source proof and inert rejection for pinned reflection compatibility.

No request, admission, authorization or lease is issued, even in an isolated
owner. Public validators remain unchanged. Constructed pinned dataclasses are
unauthenticated data used only to demonstrate rejection at the frozen boundary.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
from copy import copy, deepcopy
from dataclasses import asdict, fields
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core.runtime.synthetic import synthetic_runtime_authorization as old_auth
    from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as old_runtime
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned as pinned_auth
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned_lifecycle as pinned_runtime
    from core.runtime.synthetic import synthetic_read_only_reflection as primitive
    from core.runtime.synthetic import synthetic_reflection_execution_admission as admission
    from core.runtime.synthetic import synthetic_reflection_execution_lifecycle as reflection


ROOT = Path(__file__).resolve().parents[3]
PINNED_CONTRACT = ROOT / "docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1/contract.json"


def _tree(module):
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def _function(module, name):
    return next(node for node in _tree(module).body
        if isinstance(node, ast.FunctionDef) and node.name == name)


def _calls(node):
    return [call for call in ast.walk(node) if isinstance(call, ast.Call)]


def _call_names(module, name):
    return {ast.unparse(call.func) for call in _calls(_function(module, name))}


def _attributes(module, name):
    return {ast.unparse(node) for node in ast.walk(_function(module, name))
        if isinstance(node, ast.Attribute)}


@pytest.fixture(autouse=True)
def pure_scope():
    registries = (old_auth._ISSUED_HANDLES, old_runtime._AUTHORIZATION_LEASES,
        old_runtime._LEASES, pinned_auth._LIVE, pinned_auth.provider_owner._LIVE,
        primitive._ISSUED_REQUESTS, admission._ISSUED_ADMISSIONS,
        reflection._ADMISSION_LEASES, reflection._LEASES)
    baseline = tuple(dict(registry) for registry in registries)
    store = pinned_runtime._STORE
    store_baseline = (dict(store.authorization_leases), dict(store.leases))
    validators = ((old_auth, "validate_synthetic_runtime_authorization"),
        (old_runtime, "validate_synthetic_runtime_execution_lease"),
        (pinned_auth, "validate_pinned_synthetic_runtime_authorization"),
        (pinned_runtime, "validate_pinned_synthetic_runtime_execution_lease"),
        (primitive, "validate_synthetic_reflection_request"),
        (admission, "validate_synthetic_reflection_execution_admission"),
        (reflection, "validate_synthetic_reflection_execution_lease"))
    originals = tuple(getattr(module, name) for module, name in validators)
    with no_runtime_effects(strict=True) as evidence, ExitStack() as denials:
        # Extend the shared infrastructure guard to this audit's stricter
        # zero-capability scope. Denials never replace an authenticator.
        for module, names in (
                (old_auth, ("issue_synthetic_runtime_authorization",)),
                (pinned_auth, ("issue_pinned_synthetic_runtime_authorization",)),
                (pinned_auth.provider_owner, ("issue_pinned_java_exact_provider",)),
                (old_runtime, ("issue_synthetic_runtime_execution_lease",
                    "consume_synthetic_runtime_execution_lease",
                    "invalidate_synthetic_runtime_execution_lease", "_transition")),
                (pinned_runtime, ("issue_pinned_synthetic_runtime_execution_lease",
                    "consume_pinned_synthetic_runtime_execution_lease",
                    "invalidate_pinned_synthetic_runtime_execution_lease", "_transition")),
                (primitive, ("_issue", "executor1r_before_request", "executor1r_after_request",
                    "render_synthetic_read_only_reflection", "verify")),
                (admission, ("issue_synthetic_reflection_execution_admission", "verify")),
                (reflection, ("issue_synthetic_reflection_execution_lease",
                    "consume_synthetic_reflection_execution_lease",
                    "invalidate_synthetic_reflection_execution_lease", "_transition", "verify"))):
            for name in names:
                target = module.__name__ + "." + name
                denials.enter_context(patch.object(module, name, side_effect=evidence.deny(target)))
        yield
    assert evidence.denied_attempts == {}
    assert tuple(dict(registry) for registry in registries) == baseline
    assert pinned_runtime._STORE is store
    assert (dict(store.authorization_leases), dict(store.leases)) == store_baseline
    assert tuple(getattr(module, name) for module, name in validators) == originals


def _inert_pinned_pair():
    _, scenario = pinned_auth._scenario_identity()
    provider = pinned_auth.PinnedSyntheticProviderIdentity(**{
        item.name: "inert-not-provider-evidence"
        for item in fields(pinned_auth.PinnedSyntheticProviderIdentity)})
    authorization = pinned_auth.PinnedSyntheticRuntimeAuthorization(
        pinned_auth.OWNER_ID, "a" * 64, "b" * 64, pinned_runtime._ISSUER_PID,
        scenario, provider, "")
    lease = pinned_runtime.PinnedSyntheticRuntimeExecutionLease(
        authorization.authorization_id, "c" * 64, authorization.proof_context_id,
        pinned_runtime._ISSUER_PID, scenario, provider,
        pinned_runtime.ACTIVATION_POLICY_ID, pinned_runtime.ACTIVATION_POLICY_DIGEST,
        "d" * 64, "e" * 64, "f" * 64)
    return authorization, lease


def test_pinned_scenario_field_coincidence_preserves_separate_exact_domains():
    authorization, lease = _inert_pinned_pair()
    spec = old_auth.executor1r_decrement_3_spec()
    metadata = spec.observation_contract.requested_field_metadata
    assert (lease.scenario.scenario_id, lease.scenario.source_sha256,
        lease.scenario.source_size_bytes, lease.scenario.definition_sha256) == (
            spec.scenario_id, spec.source_sha256, spec.source_size_bytes, metadata.definition_sha256)
    assert (lease.scenario.field_owner, lease.scenario.field_name, lease.scenario.field_type) == (
        "SyntheticStateBox", "value", "int")
    assert type(lease) is pinned_runtime.PinnedSyntheticRuntimeExecutionLease
    assert not issubclass(type(lease), old_runtime.SyntheticRuntimeExecutionLease)
    assert pinned_runtime.OWNER_ID != old_runtime.__name__
    assert pinned_runtime.PHASE_ID != old_runtime.PHASE_ID
    assert pinned_runtime.SCHEMA_VERSION != old_runtime.SCHEMA_VERSION
    assert not hasattr(authorization, "issuance_id")
    assert not hasattr(lease, "upstream_authorization_issuance_id")
    assert {pinned_runtime.ISSUED, pinned_runtime.CONSUMED, pinned_runtime.INVALIDATED} == {
        old_runtime.ISSUED, old_runtime.CONSUMED, old_runtime.INVALIDATED}


@pytest.mark.parametrize("kind", ("exact_pinned", "copy", "deepcopy", "JSON", "namespace"))
def test_old_public_runtime_validator_rejects_inert_pinned_class_and_exports(kind):
    _, lease = _inert_pinned_pair()
    if kind in ("copy", "deepcopy"):
        lease = (copy if kind == "copy" else deepcopy)(lease)
    elif kind in ("JSON", "namespace"):
        payload = json.loads(json.dumps(asdict(lease)))
        lease = payload if kind == "JSON" else SimpleNamespace(**payload)
    with pytest.raises(old_runtime.SyntheticRuntimeExecutionLeaseError) as caught:
        old_runtime.validate_synthetic_runtime_execution_lease(lease)
    assert caught.value.code == "synthetic_runtime_lease_unauthenticated"
    assert caught.value.reason == "owner-issued typed live lease required"
    with pytest.raises(pinned_runtime.PinnedSyntheticRuntimeExecutionLeaseError) as caught:
        pinned_runtime.validate_pinned_synthetic_runtime_execution_lease(lease)
    assert caught.value.code == "LEASE_UNAUTHENTICATED"


@pytest.mark.parametrize("role", reflection.SUPPORTED_ROLES)
def test_frozen_reflection_rejects_pinned_authorization_before_accepting_runtime(role):
    authorization, lease = _inert_pinned_pair()
    spec = old_auth.executor1r_decrement_3_spec()
    with pytest.raises(old_auth.SyntheticRuntimeAuthorizationError) as caught:
        old_auth.validate_synthetic_runtime_authorization(authorization,
            spec=spec, source=old_auth.get_executor1r_decrement_3_source())
    assert caught.value.code == "synthetic_authorization_unauthenticated"
    assert primitive.synthetic_reflection_satisfies_authorization(None, authorization) is False
    with pytest.raises(reflection.SyntheticReflectionExecutionLeaseError) as caught:
        reflection._authenticate_inputs(None, None, lease, authorization, role)
    assert caught.value.code == "synthetic_reflection_lease_upstream_authentication_failed"
    assert caught.value.reason == "synthetic_authorization_unauthenticated"


def test_frozen_consumer_imports_public_exact_old_owner_validators():
    assert primitive.authorization_owner is admission.authorization_owner is reflection.authorization_owner is old_auth
    assert reflection.runtime_owner is old_runtime
    assert admission.reflection_owner is primitive
    assert reflection.request_owner is primitive and reflection.admission_owner is admission
    assert _call_names(reflection, "_authenticate_inputs") >= {
        "authorization_owner.validate_synthetic_runtime_authorization",
        "runtime_owner.validate_synthetic_runtime_execution_lease",
        "request_owner.validate_synthetic_reflection_request",
        "admission_owner.validate_synthetic_reflection_execution_admission",
        "admission_owner.synthetic_reflection_admission_satisfies_executor"}
    assert "authorization_owner.validate_synthetic_runtime_authorization" in _call_names(
        admission, "_validate_upstream_pair")
    assert "authorization_owner.validate_synthetic_runtime_authorization" in _call_names(
        primitive, "synthetic_reflection_satisfies_authorization")
    for module in (primitive, admission, reflection):
        assert "synthetic_runtime_authorization_pinned" not in Path(module.__file__).read_text(encoding="utf-8")


def test_exact_old_runtime_type_gate_precedes_registry_and_live_identity_checks():
    source = ast.unparse(_function(old_runtime, "_authenticated_record_locked"))
    assert source.index("type(lease) is not SyntheticRuntimeExecutionLease") < source.index("_LEASES.get")
    assert source.index("record.lease_ref() is not lease") < source.index("_authenticate_authorization(upstream)")
    assert "_AUTHORIZATION_LEASES.get(upstream.issuance_id)" in source
    auth = ast.unparse(_function(old_auth, "validate_synthetic_runtime_authorization"))
    assert "type(authorization) is not SyntheticRuntimeAuthorization" in auth
    assert "_ISSUED_HANDLES.get(authorization.issuance_id) is not authorization" in auth


def test_frozen_admission_binds_old_auth_request_renderer_but_no_runtime_lease_or_provider():
    names = {item.name for item in fields(admission.SyntheticReflectionExecutionAdmission)}
    assert names >= {"synthetic_authorization_issuance_id", "synthetic_authorization_fingerprint",
        "reflection_request_issuance_id", "reflection_request_fingerprint",
        "scenario_phase_id", "scenario_id", "source_sha256", "definition_sha256",
        "owner", "member", "declared_type", "operation", "observation_role",
        "renderer_identity", "renderer_fingerprint"}
    assert not any("runtime_execution_lease" in name or "provider" in name for name in names)
    pair = _attributes(admission, "_validate_upstream_pair")
    assert pair >= {"auth.source_kind", "auth.source_sha256", "auth.scenario_id",
        "auth.synthetic_runtime_authority", "invocation.arguments", "observation.roles"}
    issue = _attributes(admission, "issue_synthetic_reflection_execution_admission")
    assert issue >= {"auth.issuance_id", "auth.fingerprint", "request.issuance_id", "request.fingerprint"}
    source = Path(admission.__file__).read_text(encoding="utf-8")
    assert "synthetic_runtime_authorization_lifecycle" not in source
    assert "runtime_java" not in source


def test_reflection_lease_projects_runtime_and_old_authorization_identity():
    projections = _attributes(reflection, "_unsigned_lease")
    assert projections >= {"runtime.lease_id", "runtime.fingerprint", "authorization.issuance_id",
        "authorization.fingerprint", "admission.admission_id", "admission.fingerprint",
        "request.issuance_id", "request.fingerprint"}
    bindings = _attributes(reflection, "_authenticate_inputs")
    assert bindings >= {"runtime.upstream_authorization_issuance_id",
        "runtime.upstream_authorization_fingerprint", "authorization.issuance_id",
        "authorization.fingerprint", "capability.scenario_id", "capability.source_sha256",
        "capability.observation_role", "capability.definition_sha256"}
    source = ast.unparse(_function(reflection, "_bound_record_locked"))
    assert all(name + " is not record." + name in source
        for name in ("admission", "request", "runtime", "authorization"))
    assert "role != record.observation_role" in source


def test_reflection_validation_reauthenticates_live_upstreams_and_signed_current_state():
    record = ast.unparse(_function(reflection, "_authenticated_record_locked"))
    assert "type(lease) is not SyntheticReflectionExecutionLease" in record
    assert "record.lease_ref() is not lease" in record
    assert "_authenticate_inputs(record.admission, record.request, record.runtime, record.authorization, record.observation_role)" in record
    assert "_ADMISSION_LEASES.get(record.admission.admission_id) != lease.lease_id" in record
    assert "record.lifecycle_state not in (ISSUED, CONSUMED, INVALIDATED)" in record
    assert "hmac.compare_digest(record.signature, _sign(record.projection_json, record.lifecycle_state))" in record
    for name in ("validate_synthetic_reflection_execution_lease", "synthetic_reflection_execution_lease_state"):
        assert "_authenticated_record_locked" in _call_names(reflection, name)
    for module, registry in ((old_runtime, "_LEASES"), (pinned_runtime, "_STORE.leases")):
        source = ast.unparse(_function(module, "_authenticated_record_locked"))
        assert registry + ".get(lease.lease_id)" in source
        assert "record.lease_ref() is not lease" in source
        assert "hmac.compare_digest" in source


def test_runtime_state_is_authenticated_through_old_public_state_api():
    assert "runtime_owner.synthetic_runtime_execution_lease_state" in _call_names(reflection, "_runtime_state")
    assert "state != required" in ast.unparse(_function(reflection, "_runtime_state"))
    for module, name in ((old_runtime, "synthetic_runtime_execution_lease_state"),
            (pinned_runtime, "pinned_synthetic_runtime_execution_lease_state")):
        node = _function(module, name)
        assert "_authenticated_record_locked" in {ast.unparse(call.func) for call in _calls(node)}
        assert any(isinstance(item, ast.With) and "_local_lock" in ast.unparse(item.items[0].context_expr)
            for item in ast.walk(node))


def test_issuance_and_precheck_require_issued_runtime_for_both_roles():
    issue = _function(reflection, "issue_synthetic_reflection_execution_lease")
    state_check = next(call for call in _calls(issue) if ast.unparse(call.func) == "_runtime_state")
    assert [ast.unparse(arg) for arg in state_check.args] == ["runtime", "authorization", "ISSUED"]
    source = ast.unparse(issue)
    assert source.index("_authenticate_inputs(") < source.index("_runtime_state(") < source.index("_LEASES[lease_id] = record")
    ready = _function(reflection, "synthetic_reflection_execution_lease_satisfies_executor")
    call = next(call for call in _calls(ready) if ast.unparse(call.func) == "_compatible")
    assert ast.unparse(call.args[-1]) == "ISSUED"
    compatible = ast.unparse(_function(reflection, "_compatible"))
    assert "record.lifecycle_state == ISSUED" in compatible
    assert "_bound_record_locked" in compatible and "_runtime_state" in compatible
    assert "BEFORE_ROLE" not in source and "AFTER_ROLE" not in source


def test_active_precheck_and_reflection_consumption_require_consumed_runtime_for_both_roles():
    active = _function(reflection, "consumable_during_active_execution")
    call = next(call for call in _calls(active) if ast.unparse(call.func) == "_compatible")
    assert ast.unparse(call.args[-1]) == "CONSUMED"
    transition = ast.unparse(_function(reflection, "_transition"))
    assert "record.lifecycle_state != ISSUED" in transition
    assert "if target == CONSUMED:" in transition
    assert "_runtime_state(runtime, authorization, CONSUMED)" in transition
    assert transition.index("_bound_record_locked(") < transition.index("_runtime_state(") < transition.index("_LEASES[lease.lease_id] = updated")
    assert "BEFORE_ROLE" not in transition and "AFTER_ROLE" not in transition
    consume = _function(reflection, "consume_synthetic_reflection_execution_lease")
    call = next(call for call in _calls(consume) if ast.unparse(call.func) == "_transition")
    assert ast.unparse(call.args[-1]) == "CONSUMED"
    assert not any("consume_synthetic_runtime_execution_lease" in ast.unparse(call.func)
        for call in _calls(consume) + _calls(_function(reflection, "_transition")))


def test_before_after_sequence_preserves_pinned_first_behavior_boundary_and_compile_dependency():
    sequence = reflection.EXECUTOR_SEQUENCE
    assert sequence == (
        "all capability/authentication gates", "source/harness ready",
        "consume scenario runtime lease", "consume BEFORE reflection lease",
        "perform BEFORE exact reflection read", "invoke exact public decrement(3)",
        "consume AFTER reflection lease", "perform AFTER exact reflection read")
    contract = json.loads(PINNED_CONTRACT.read_text(encoding="utf-8"))
    boundary = contract["consumption_boundary"]
    assert boundary["point"] == "immediately before the first behavioral runtime effect, after all authenticated consumer readiness gates"
    assert boundary["terminal_commit_precedes_effect"] is True
    assert sequence.index("consume scenario runtime lease") < sequence.index("perform BEFORE exact reflection read")
    assert sequence.index("perform BEFORE exact reflection read") < sequence.index("invoke exact public decrement(3)") < sequence.index("perform AFTER exact reflection read")
    assert boundary["source_harness_readiness_before_consumption"] is True
    assert boundary["actual_source_projection_position"] == boundary["scenario_compile_position"] == "UNRESOLVED_DOWNSTREAM_DEPENDENCY"
    assert contract["authority"]["compilation_authority"] is False
    assert "PROOF_UNRESOLVED" in ast.unparse(_function(pinned_runtime, "_consumer_readiness"))
    readiness = ast.unparse(_function(pinned_runtime, "check_pinned_synthetic_runtime_execution_lease_preconditions"))
    assert "record.lifecycle_state == ISSUED, False" in readiness


@pytest.mark.parametrize("helper_name", ("_BEFORE_HELPER", "_AFTER_HELPER"))
def test_exact_read_primitive_literals_are_authorization_epoch_independent(helper_name):
    helper = getattr(primitive, helper_name)
    assert "Class<?> owner = SyntheticStateBox.class;" in helper
    assert 'owner.getDeclaredField("value")' in helper
    assert "field.setAccessible(true);" in helper
    assert "int observed = field.getInt(instance);" in helper
    assert all(token not in helper for token in ("authorization", "lease", "provider", "schema", "decrement",
        "getDeclaredFields", "setInt", "getDeclaredMethods", "getDeclaredConstructors", "Class.forName"))
    assert not _call_names(primitive, "validate_synthetic_private_field_observation") & {
        "authorization_owner.validate_synthetic_runtime_authorization",
        "runtime_owner.validate_synthetic_runtime_execution_lease"}
    renderer = _call_names(primitive, "render_synthetic_read_only_reflection")
    assert renderer == {"validate_synthetic_reflection_request"}
    assert "authorization_owner.SyntheticRuntimeAuthorization" in ast.unparse(
        _function(primitive, "synthetic_reflection_satisfies_authorization"))


def test_positive_frozen_lifecycle_and_reflection_verifiers_are_outside_zero_issuance_scope():
    for module, required in ((primitive, {"executor1r_before_request", "executor1r_after_request",
            "authorization_owner.issue_synthetic_runtime_authorization"}),
            (admission, {"_issue_upstream", "issue_synthetic_reflection_execution_admission"}),
            (reflection, {"authorization_owner.issue_synthetic_runtime_authorization",
                "runtime_owner.issue_synthetic_runtime_execution_lease",
                "admission_owner.issue_synthetic_reflection_execution_admission",
                "issue_synthetic_reflection_execution_lease"})):
        assert required <= _call_names(module, "verify")
    tree = ast.parse((ROOT / "tests/runtime/synthetic/test_synthetic_runtime_authorization_pinned_lifecycle.py").read_text(encoding="utf-8"))
    isolated_issue = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_lease")
    assert "inert.owner.issue_pinned_synthetic_runtime_execution_lease" in {
        ast.unparse(call.func) for call in _calls(isolated_issue)}
    frozen_test = ast.parse((ROOT / "tests/runtime/synthetic/test_synthetic_reflection_execution_lifecycle.py").read_text(encoding="utf-8"))
    activation = next(node for node in frozen_test.body if isinstance(node, ast.FunctionDef) and node.name == "_activation")
    assert {"auth_owner.issue_synthetic_runtime_authorization", "runtime_owner.issue_synthetic_runtime_execution_lease"} <= {
        ast.unparse(call.func) for call in _calls(activation)}


@pytest.mark.parametrize("module_name,reason", (
    ("behavioral_diagnostic_executor_refresh", "existing_synthetic_issuer_cannot_reconstruct_independent_scenario"),
    ("behavioral_diagnostic_executor_retry", "frozen_synth_auth_1_has_no_public_consumption_contract"),
    ("behavioral_diagnostic_executor_lifecycle_retry", "java_profile_contract_mismatch")))
def test_historical_executor_blocked_semantics_remain_source_only(module_name, reason):
    tree = ast.parse((ROOT / "core" / (module_name + ".py")).read_text(encoding="utf-8"))
    verify = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "verify")
    constants = {node.value for node in ast.walk(verify) if isinstance(node, ast.Constant)
        and type(node.value) is str}
    assert reason in constants
    calls = {ast.unparse(call.func) for call in _calls(verify)}
    assert not any("consume_" in name or "invalidate_" in name or "subprocess" in name
        or name.startswith(("execute_", "run_")) for name in calls)
    source = ast.unparse(verify)
    if module_name == "behavioral_diagnostic_executor_refresh":
        assert "'source_projected': False" in source
        assert "'measured_observations': None" in source
        assert not any("issue_synthetic_runtime_authorization" in name for name in calls)
    else:
        assert "authorization.issue_synthetic_runtime_authorization" in calls
        # Even blocked retries issue capabilities, so invoking their verifier
        # would violate the audit's zero-issuance condition.
        empty = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_empty_report")
        assert "'source_projected': False" in ast.unparse(empty)
        if module_name == "behavioral_diagnostic_executor_retry":
            assert "'executor_local_substitute_permitted': False" in source
            assert "status=BLOCKED_AUTH_LIFECYCLE" in source
        else:
            assert "java_profile_contract_audit" in calls
            assert "runtime.issue_synthetic_runtime_execution_lease" in calls
            assert "reflection_lifecycle.issue_synthetic_reflection_execution_lease" in calls
            assert "infrastructure_contract_changed_requires_review" in constants
