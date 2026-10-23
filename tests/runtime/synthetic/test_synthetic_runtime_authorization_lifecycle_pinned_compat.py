"""Pure compatibility evidence; no registered handles, issuers or transitions.

The constructed dataclasses below are deliberately unauthenticated projections.
No public validator is replaced, and no private authentication registry is seeded.
"""
from __future__ import annotations

import ast
from copy import copy, deepcopy
from dataclasses import asdict, fields, replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core.runtime.synthetic import synthetic_runtime_authorization as old
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned as pinned
    from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as lifecycle
    from core.runtime.synthetic import synthetic_reflection_execution_lifecycle as reflection


ROOT = Path(__file__).resolve().parents[3]


def _function(module, name):
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def _calls(module, name):
    return {ast.unparse(node.func) for node in ast.walk(_function(module, name))
        if isinstance(node, ast.Call)}


@pytest.fixture(autouse=True)
def pure_scope():
    registries = (old._ISSUED_HANDLES, pinned._LIVE,
        lifecycle._AUTHORIZATION_LEASES, lifecycle._LEASES, reflection._LEASES)
    before = [dict(registry) for registry in registries]
    with no_runtime_effects(strict=True) as evidence:
        yield
    assert evidence.denied_attempts == {}
    assert [dict(registry) for registry in registries] == before


def _old_projection():
    spec = old.executor1r_decrement_3_spec()
    return old.SyntheticRuntimeAuthorization("a" * 64, old._ISSUER_PID,
        spec.fingerprint, spec.source_sha256, spec.source_size_bytes, spec.phase_id,
        spec.scenario_id, spec.sandbox_profile_id, spec.sandbox_policy_sha256,
        spec.java_profile_id, spec.java_schema_version, spec.source_kind,
        spec.allowed_runtime_operations)


def _pinned_projection():
    _, scenario = pinned._scenario_identity()
    provider_values = {item.name: "inert-not-a-provider-proof"
        for item in fields(pinned.PinnedSyntheticProviderIdentity)}
    provider_values.update(requirement_profile="RUNTIME.JAVA.PINNED.1",
        requirement_schema="runtime_java_pinned_1_v1")
    provider = pinned.PinnedSyntheticProviderIdentity(**provider_values)
    return pinned.PinnedSyntheticRuntimeAuthorization(pinned.OWNER_ID, "b" * 64,
        "c" * 64, pinned._ISSUER_PID, scenario, provider, "d" * 64)


def test_exact_scenario_equality_does_not_equal_authorization_epoch():
    spec, scenario = pinned._scenario_identity()
    invocation, observation = spec.invocation_contract, spec.observation_contract
    metadata = observation.requested_field_metadata
    assert asdict(scenario) == {
        "scenario_id": spec.scenario_id, "source_sha256": spec.source_sha256,
        "source_size_bytes": spec.source_size_bytes, "definition_sha256": metadata.definition_sha256,
        "class_name": invocation.owner, "method_name": invocation.public_method,
        "method_signature": "boolean SyntheticStateBox.decrement(int)",
        "arguments": invocation.arguments, "argument_types": invocation.argument_types,
        "return_type": invocation.return_type, "field_owner": metadata.owner,
        "field_name": metadata.member, "field_type": metadata.declared_type,
        "expected_before": observation.expected_before,
        "expected_return": observation.expected_return, "expected_after": observation.expected_after,
    }
    assert old.SyntheticRuntimeAuthorization is not pinned.PinnedSyntheticRuntimeAuthorization
    assert old.PHASE_ID != pinned.PHASE_ID
    assert old.AUTHORIZATION_SCHEMA_VERSION != pinned.SCHEMA_VERSION
    assert (spec.java_profile_id, spec.java_schema_version) != (
        pinned.REQUIREMENT.java_profile_id, pinned.REQUIREMENT.java_schema_version)


@pytest.mark.parametrize("kind", ("old", "pinned", "wrong_owner", "wrong_schema",
    "wrong_domain", "copy", "deepcopy", "json", "namespace"))
def test_unregistered_projections_cannot_cross_frozen_authentication_boundary(kind):
    value = _old_projection() if kind == "old" else _pinned_projection()
    if kind == "wrong_owner":
        value = replace(value, owner_identity="core.synthetic_runtime_authorization")
    elif kind == "wrong_schema":
        object.__setattr__(value, "schema_version", old.AUTHORIZATION_SCHEMA_VERSION)
    elif kind == "wrong_domain":
        value = replace(value, _signature="0" * 64)
    elif kind in ("copy", "deepcopy"):
        value = (copy if kind == "copy" else deepcopy)(value)
    elif kind in ("json", "namespace"):
        payload = json.loads(json.dumps(asdict(value)))
        value = payload if kind == "json" else SimpleNamespace(**payload)
    with pytest.raises(lifecycle.SyntheticRuntimeExecutionLeaseError) as caught:
        lifecycle._authenticate_authorization(value)
    assert caught.value.code == "synthetic_runtime_lease_upstream_authentication_failed"
    assert caught.value.reason == "synthetic_authorization_unauthenticated"
    with pytest.raises(pinned.PinnedSyntheticAuthorizationError):
        pinned.validate_pinned_synthetic_runtime_authorization(value)


def test_lifecycle_calls_exact_old_public_validator_and_old_owner_projections():
    assert lifecycle.authorization_owner is old
    assert _calls(lifecycle, "_authenticate_authorization") >= {
        "authorization_owner.executor1r_decrement_3_spec",
        "authorization_owner.get_executor1r_decrement_3_source",
        "authorization_owner.validate_synthetic_runtime_authorization",
    }
    assert "_authenticate_authorization" in _calls(lifecycle, "_authenticated_record_locked")
    assert "_authenticate_authorization" in _calls(lifecycle, "issue_synthetic_runtime_execution_lease")
    text = ast.unparse(_function(lifecycle, "_unsigned_lease"))
    assert "authorization.issuance_id" in text and "authorization.fingerprint" in text
    assert not hasattr(_pinned_projection(), "issuance_id")


@pytest.mark.parametrize("name", ("validate_synthetic_runtime_execution_lease",
    "synthetic_runtime_execution_lease_state", "synthetic_runtime_execution_lease_satisfies_executor",
    "_transition"))
def test_each_record_consumer_reauthenticates_under_the_owner_lock(name):
    assert "_authenticated_record_locked" in _calls(lifecycle, name)
    node = _function(lifecycle, name)
    locked = [item for item in ast.walk(node) if isinstance(item, ast.With)
        and any(ast.unparse(context.context_expr) == "_local_lock()" for context in item.items)]
    assert locked
    assert any("_authenticated_record_locked" in {ast.unparse(call.func)
        for call in ast.walk(block) if isinstance(call, ast.Call)} for block in locked)


def test_hmac_algorithm_equality_preserves_separate_owner_domains():
    assert old._SECRET is not pinned._SECRET
    assert pinned._DOMAIN == b"CATTUS:SYNTH.AUTH.PINNED.1:exact-scenario-authorization:v1\x00"
    old_sign, new_sign = (ast.unparse(_function(module, "_sign")) for module in (old, pinned))
    assert "hmac.new" in old_sign and "hmac.new" in new_sign
    assert "_DOMAIN" not in old_sign
    assert "_DOMAIN" in new_sign and "authorization-hmac" in new_sign
    assert "_authenticate_provider" in _calls(pinned, "validate_pinned_synthetic_runtime_authorization")


def test_state_machine_tombstones_and_terminal_commit_have_no_provider_logic():
    issue = ast.unparse(_function(lifecycle, "issue_synthetic_runtime_execution_lease"))
    transition = ast.unparse(_function(lifecycle, "_transition"))
    assert "authorization.issuance_id in _AUTHORIZATION_LEASES" in issue
    assert "_AUTHORIZATION_LEASES[authorization.issuance_id] = lease_id" in issue
    assert "target not in (CONSUMED, INVALIDATED)" in transition
    assert "record.lifecycle_state != ISSUED" in transition
    assert "_LEASES[lease.lease_id] = updated" in transition
    assert "replace" in _calls(lifecycle, "_transition")
    for name in ("_transition", "_authenticate_authorization", "_authenticated_record_locked"):
        assert not any("provider" in call or "java" in call.lower() for call in _calls(lifecycle, name))
    assert not any(name.startswith(("reset_", "refund_", "restore_")) for name in vars(lifecycle))


def test_reflection_keeps_frozen_authentication_and_runtime_state_contracts():
    assert reflection.authorization_owner is old
    assert reflection.runtime_owner is lifecycle
    assert _calls(reflection, "_authenticate_inputs") >= {
        "authorization_owner.validate_synthetic_runtime_authorization",
        "runtime_owner.validate_synthetic_runtime_execution_lease",
    }
    assert "runtime_owner.synthetic_runtime_execution_lease_state" in _calls(reflection, "_runtime_state")
    assert "ISSUED" in ast.unparse(_function(reflection, "issue_synthetic_reflection_execution_lease"))
    assert "CONSUMED" in ast.unparse(_function(reflection, "consumable_during_active_execution"))
    assert "CONSUMED" in ast.unparse(_function(reflection, "_transition"))
    required = {"upstream_authorization_issuance_id", "upstream_authorization_fingerprint",
        "scenario_phase_id", "scenario_id", "source_sha256", "lease_id", "issuing_process_id"}
    assert required <= {item.name for item in fields(lifecycle.SyntheticRuntimeExecutionLease)}
    assert reflection.EXECUTOR_SEQUENCE.index("invoke exact public decrement(3)") == 5


def test_frozen_reflection_tests_require_issuance_and_are_not_zero_issuance_fixtures():
    tree = ast.parse((ROOT / "tests/runtime/synthetic/test_synthetic_reflection_execution_lifecycle.py").read_text(encoding="utf-8"))
    activation = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_activation")
    calls = {ast.unparse(node.func) for node in ast.walk(activation) if isinstance(node, ast.Call)}
    assert "auth_owner.issue_synthetic_runtime_authorization" in calls
    assert "runtime_owner.issue_synthetic_runtime_execution_lease" in calls


def test_inert_lease_cannot_establish_runtime_or_reflection_identity():
    auth = _old_projection()
    lease = lifecycle.SyntheticRuntimeExecutionLease(auth.issuance_id, "0" * 64,
        lifecycle.SCENARIO_PHASE_ID, lifecycle.SCENARIO_ID, lifecycle.SOURCE_KIND,
        lifecycle.SOURCE_SHA256, lifecycle.INVOCATION_OWNER, lifecycle.INVOCATION_METHOD,
        lifecycle.INVOCATION_ARGUMENT, "e" * 64, lifecycle._ISSUER_PID)
    with pytest.raises(lifecycle.SyntheticRuntimeExecutionLeaseError):
        lifecycle.validate_synthetic_runtime_execution_lease(lease, auth)
    assert lifecycle.synthetic_runtime_execution_lease_satisfies_executor(lease, auth) is False
    with pytest.raises(reflection.SyntheticReflectionExecutionLeaseError):
        reflection._authenticate_inputs(None, None, lease, auth, reflection.BEFORE_ROLE)
