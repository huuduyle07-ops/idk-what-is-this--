"""Exact pinned scenario scope through the unchanged public provider issuers.

The imported transports are virtual fixtures. A strict effect guard stays in
place throughout issuance, so these tests cannot launch Docker, Java, shell,
network, reflection, or a behavioral scenario.
"""
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
import hashlib
import inspect
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned as owner
    from core.runtime.synthetic import synthetic_runtime_authorization as historical
    from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as lifecycle
    from core.runtime.synthetic import synthetic_read_only_reflection as reflection
    from core import runtime_java_pinned_provider as provider
    from tests.test_runtime_java_pinned_provider import (
        guarded, control, runtime_control, _upstreams,
    )


_FALSE_AUTHORITIES = (
    "runtime_execution_authority", "execution_lease_authority",
    "reflection_execution_authority", "real_task_runtime_authority",
    "repository_write_authority", "apply_authority", "network_authority",
    "host_mount_authority", "shell_authority", "arbitrary_command_authority",
    "executor_authority", "BANK_authority", "arbitrary_java_authority",
    "arbitrary_class_authority", "arbitrary_method_authority",
    "arbitrary_source_authority", "repository_java_authority",
)
_FALSE_PROVIDER_AUTHORITIES = (
    "runtime_authority", "real_task_runtime_authority", "repository_write_authority",
    "apply_authority", "compatibility_authority", "SYNTH_authority", "executor_authority",
)
_SCENARIO_FIELDS = (
    "scenario_id", "source_sha256", "source_size_bytes", "definition_sha256",
    "class_name", "method_name", "method_signature", "arguments", "argument_types",
    "return_type", "field_owner", "field_name", "field_type", "expected_before",
    "expected_return", "expected_after",
)
_PROVIDER_FIELDS = (
    "phase_id", "schema_version", "owner_identity", "proof_context_identity",
    "receipt_id", "fingerprint", "evidence_digest", "requirement_profile",
    "requirement_schema", "target_image_identity", "runtime_sandbox_profile",
    "runtime_sandbox_policy_sha256", "controller_identity_evidence_json",
    "cleanup_evidence_json", "cleanup_evidence_digest",
)


class _StringSubclass(str):
    pass


def _different(value):
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return value + "_changed"
    if type(value) is tuple:
        return value + ("unexpected",)
    if is_dataclass(value):
        first = fields(value)[0].name
        return replace(value, **{first: _different(getattr(value, first))})
    raise AssertionError("Unexpected immutable authorization field: " + repr(type(value)))


@contextmanager
def _temporarily_set(value, field, changed):
    original = getattr(value, field)
    object.__setattr__(value, field, changed)
    try:
        yield
    finally:
        object.__setattr__(value, field, original)


def _assert_rejected(candidate):
    with pytest.raises(ValueError):
        owner.validate_pinned_synthetic_runtime_authorization(candidate)


@pytest.fixture(autouse=True)
def isolated_authorizations(guarded):
    with patch.dict(owner._LIVE, {}, clear=True):
        yield


@pytest.fixture
def issued(runtime_control, isolated_authorizations):
    outcome = owner.issue_pinned_synthetic_runtime_authorization()
    assert outcome.status == owner.COMPLETE, outcome.reason
    assert outcome.authorization is not None
    assert outcome.provider_outcome is not None
    assert owner.validate_pinned_synthetic_runtime_authorization(outcome.authorization) is outcome.authorization
    return outcome


def test_new_epoch_uses_exact_historical_source_and_scenario(issued):
    auth = issued.authorization
    scenario = auth.scenario
    original = historical.executor1r_decrement_3_spec()
    source = historical.get_executor1r_decrement_3_source()
    invocation = original.invocation_contract
    observation = original.observation_contract
    metadata = observation.requested_field_metadata
    assert owner.PHASE_ID == auth.phase_id == "SYNTH.AUTH.PINNED.1"
    assert owner.SCHEMA_VERSION == auth.schema_version == "synthetic_runtime_authorization_pinned_1_v1"
    assert owner.COMPLETE == issued.status == "SYNTH_AUTH_PINNED_1_COMPLETE"
    assert scenario.scenario_id == original.scenario_id == "synthetic.EXECUTOR.1R.decrement_3"
    assert scenario.source_sha256 == original.source_sha256 == hashlib.sha256(source).hexdigest()
    assert scenario.source_sha256 == "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
    assert scenario.source_size_bytes == original.source_size_bytes == len(source) == 239
    assert scenario.definition_sha256 == metadata.definition_sha256
    assert scenario.definition_sha256 == "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d"
    assert scenario.class_name == invocation.owner == "SyntheticStateBox"
    assert scenario.method_name == invocation.public_method == "decrement"
    assert scenario.arguments == invocation.arguments == (3,)
    assert scenario.argument_types == invocation.argument_types == ("int",)
    assert scenario.return_type == invocation.return_type == "boolean"
    assert scenario.field_owner == metadata.owner == "SyntheticStateBox"
    assert scenario.field_name == metadata.member == "value"
    assert scenario.field_type == metadata.declared_type == "int"
    assert scenario.expected_before == observation.expected_before == 10
    assert scenario.expected_return is observation.expected_return is True
    assert scenario.expected_after == observation.expected_after == 7
    assert scenario.method_signature == "boolean SyntheticStateBox.decrement(int)"
    assert original.java_profile_id == "RUNTIME.JAVA.1"
    assert original.java_schema_version == "runtime_java_1_v1"
    assert auth.provider.requirement_profile == "RUNTIME.JAVA.PINNED.1"
    assert auth.provider.requirement_schema == "runtime_java_pinned_1_v1"
    assert auth.provider.requirement_profile != original.java_profile_id
    assert auth.provider.requirement_schema != original.java_schema_version


def test_scope_is_authorization_only_and_public_objects_are_immutable(issued):
    auth = issued.authorization
    assert auth.synthetic_scenario_authorized is True
    assert all(getattr(auth, field) is False for field in _FALSE_AUTHORITIES)
    assert auth.lifecycle_compatibility_evaluated is False
    assert auth.lifecycle_execution_ready is False
    root = issued.provider_outcome.receipt
    assert root.status == provider.COMPLETE
    assert root.exact_provider_proven is True
    assert all(getattr(root, field) is False for field in _FALSE_PROVIDER_AUTHORITIES)
    for value in (auth, auth.scenario, auth.provider):
        name = fields(value)[0].name
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(value, name, _different(getattr(value, name)))
    assert not any(hasattr(auth, field) for field in
        ("consume", "lease_id", "lifecycle_state", "runtime_authority"))
    for name in ("authorization_id", "proof_context_id", "evidence_digest", "fingerprint"):
        value = getattr(auth, name)
        assert type(value) is str and len(value) == 64
    assert auth.issuing_pid == owner.os.getpid()


def test_fresh_issuance_reauthenticates_the_exact_live_provider_graph(runtime_control, monkeypatch):
    calls = []
    original = provider.validate_pinned_java_exact_provider

    def observe(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(provider, "validate_pinned_java_exact_provider", observe)
    outcome = owner.issue_pinned_synthetic_runtime_authorization()
    assert outcome.status == owner.COMPLETE, outcome.reason
    auth = outcome.authorization
    expected = (outcome.provider_outcome.receipt, *_upstreams(outcome.provider_outcome))
    assert any(len(args) == len(expected) and all(a is b for a, b in zip(args, expected)) for args in calls)
    calls.clear()
    before = deepcopy(outcome.as_dict())
    command_count = len(runtime_control.commands)
    for _ in range(3):
        assert owner.validate_pinned_synthetic_runtime_authorization(auth) is auth
    assert len(calls) >= 3
    assert all(len(args) == len(expected) and all(a is b for a, b in zip(args, expected)) for args in calls)
    assert len(runtime_control.commands) == command_count
    assert outcome.as_dict() == before
    assert runtime_control.sandbox_runs == 1
    assert sum(command[0] == "start" for command, _ in runtime_control.commands) == 1


def test_public_issuer_accepts_no_free_form_inputs(runtime_control):
    assert not inspect.signature(owner.issue_pinned_synthetic_runtime_authorization).parameters
    for supplied in (None, {}, "caller-provider-fingerprint", historical.executor1r_decrement_3_spec()):
        with pytest.raises(TypeError):
            owner.issue_pinned_synthetic_runtime_authorization(supplied)
    for keyword in ("source", "scenario", "provider", "fingerprint", "class_name", "method", "argument", "field"):
        with pytest.raises(TypeError):
            owner.issue_pinned_synthetic_runtime_authorization(**{keyword: "caller-defined"})
    assert runtime_control.commands == [] and runtime_control.sandbox_runs == 0


@pytest.mark.parametrize("kind", ("copy", "deepcopy", "replace", "constructor", "json", "wrapper", "subclass"))
def test_matching_authorization_projection_never_recreates_authority(issued, kind):
    auth = issued.authorization
    if kind == "copy":
        candidate = copy(auth)
    elif kind == "deepcopy":
        candidate = deepcopy(auth)
    elif kind == "replace":
        candidate = replace(auth)
    elif kind == "json":
        candidate = json.loads(json.dumps(auth.as_dict()))
    elif kind == "wrapper":
        candidate = SimpleNamespace(**auth.as_dict())
    else:
        cls = type(auth)
        if kind == "subclass":
            class Subclass(cls):
                pass
            cls = Subclass
        candidate = cls(**{field.name: getattr(auth, field.name) for field in fields(auth) if field.init})
    _assert_rejected(candidate)
    assert owner.validate_pinned_synthetic_runtime_authorization(auth) is auth


@pytest.mark.parametrize("field", tuple(field.name for field in fields(owner.PinnedSyntheticRuntimeAuthorization)))
def test_every_authorization_field_is_authenticated(issued, field):
    auth = issued.authorization
    with _temporarily_set(auth, field, _different(getattr(auth, field))):
        _assert_rejected(auth)
    assert owner.validate_pinned_synthetic_runtime_authorization(auth) is auth


@pytest.mark.parametrize("field", _SCENARIO_FIELDS)
def test_every_frozen_scenario_identity_and_expectation_is_authenticated(issued, field):
    auth = issued.authorization
    with _temporarily_set(auth.scenario, field, _different(getattr(auth.scenario, field))):
        _assert_rejected(auth)
    assert owner.validate_pinned_synthetic_runtime_authorization(auth) is auth


@pytest.mark.parametrize("field", _PROVIDER_FIELDS)
def test_every_provider_identity_policy_controller_and_cleanup_projection_is_authenticated(issued, field):
    auth = issued.authorization
    with _temporarily_set(auth.provider, field, _different(getattr(auth.provider, field))):
        _assert_rejected(auth)
    assert owner.validate_pinned_synthetic_runtime_authorization(auth) is auth


@pytest.mark.parametrize("target,field,value", (
    ("authorization", "synthetic_scenario_authorized", 1),
    ("authorization", "runtime_execution_authority", 0),
    ("authorization", "issuing_pid", True),
    ("scenario", "arguments", (True,)),
    ("scenario", "arguments", (3.0,)),
    ("scenario", "arguments", [3]),
    ("scenario", "argument_types", ["int"]),
    ("scenario", "expected_before", 10.0),
    ("scenario", "expected_return", 1),
    ("scenario", "expected_after", 7.0),
    ("scenario", "scenario_id", _StringSubclass("synthetic.EXECUTOR.1R.decrement_3")),
    ("provider", "requirement_profile", _StringSubclass("RUNTIME.JAVA.PINNED.1")),
    ("provider", "requirement_profile", "RUNTIME.JAVA.1"),
    ("provider", "requirement_schema", "runtime_java_1_v1"),
))
def test_python_equality_aliases_and_historical_requirements_are_rejected(issued, target, field, value):
    auth = issued.authorization
    obj = auth if target == "authorization" else getattr(auth, target)
    with _temporarily_set(obj, field, value):
        _assert_rejected(auth)


@pytest.mark.parametrize("field,value", (
    ("receipt_id", "0" * 64), ("proof_context_identity", "0" * 64),
    ("evidence_digest", "0" * 64), ("_signature", "0" * 64),
    ("exact_provider_proven", False),
    ("requirement_profile", "RUNTIME.JAVA.1"),
    ("requirement_schema", "runtime_java_1_v1"),
    *[(field, True) for field in _FALSE_PROVIDER_AUTHORITIES],
))
def test_provider_root_is_live_reauthenticated_after_authorization_issuance(issued, field, value):
    auth = issued.authorization
    with _temporarily_set(issued.provider_outcome.receipt, field, value):
        _assert_rejected(auth)
    assert owner.validate_pinned_synthetic_runtime_authorization(auth) is auth


@pytest.mark.parametrize("role,field,value", (
    (0, "canonical_backend_route_identity", "caller-alias"),
    (4, "controller_source_identity", ()), (4, "cleanup_evidence", ()),
    (5, "verification_receipt_fingerprint", "0" * 64),
    (6, "java_sha256", "0" * 64), (6, "javac_sha256", "0" * 64),
    (7, "seccomp_policy_sha256", "0" * 64), (8, "cleanup_verified", False),
))
def test_provider_upstream_graph_remains_required_by_new_authorization(issued, role, field, value):
    upstream = _upstreams(issued.provider_outcome)[role]
    with _temporarily_set(upstream, field, value):
        _assert_rejected(issued.authorization)
    assert owner.validate_pinned_synthetic_runtime_authorization(issued.authorization) is issued.authorization


@pytest.mark.parametrize("kind", ("copy", "deepcopy", "replace", "json", "fingerprint", "receipt_id", "chronology"))
def test_caller_provider_aliases_and_projected_outcomes_cannot_replace_retained_graph(issued, kind):
    original = issued.provider_outcome
    if kind == "copy":
        candidate = copy(original)
    elif kind == "deepcopy":
        candidate = deepcopy(original)
    elif kind == "replace":
        candidate = replace(original)
    elif kind == "json":
        candidate = json.loads(json.dumps(original.as_dict()))
    elif kind == "fingerprint":
        candidate = original.receipt.fingerprint
    elif kind == "receipt_id":
        candidate = original.receipt.receipt_id
    else:
        candidate = SimpleNamespace(status=provider.COMPLETE, happened_after_pinned1b=True)
    with pytest.raises(ValueError):
        owner.validate_pinned_synthetic_runtime_authorization(issued.authorization, provider_outcome=candidate)
    assert owner.validate_pinned_synthetic_runtime_authorization(
        issued.authorization, provider_outcome=original) is issued.authorization


def test_different_authentic_provider_cannot_be_substituted(issued, runtime_control):
    other = provider.issue_pinned_java_exact_provider()
    assert other.status == provider.COMPLETE, other.reason
    assert other.receipt is not issued.provider_outcome.receipt
    with pytest.raises(ValueError):
        owner.validate_pinned_synthetic_runtime_authorization(issued.authorization, provider_outcome=other)
    assert owner.validate_pinned_synthetic_runtime_authorization(issued.authorization) is issued.authorization


@pytest.mark.parametrize("field", ("receipt", "runtime_descriptor", "runtime_receipt", "sandbox_descriptor", "sandbox_receipt", "attachment"))
def test_provider_outcome_retains_each_original_root_and_upstream_identity(issued, field):
    original = issued.provider_outcome
    with _temporarily_set(original, field, copy(getattr(original, field))):
        _assert_rejected(issued.authorization)
    assert owner.validate_pinned_synthetic_runtime_authorization(issued.authorization) is issued.authorization


def test_old_authorization_epoch_and_lifecycle_do_not_accept_new_scope(issued):
    spec = historical.executor1r_decrement_3_spec()
    source = historical.get_executor1r_decrement_3_source()
    old = historical.issue_synthetic_runtime_authorization(spec, source=source)
    _assert_rejected(old)
    with pytest.raises(historical.SyntheticRuntimeAuthorizationError):
        historical.validate_synthetic_runtime_authorization(issued.authorization, spec=spec, source=source)
    with pytest.raises(lifecycle.SyntheticRuntimeExecutionLeaseError):
        lifecycle.issue_synthetic_runtime_execution_lease(issued.authorization)
    request = reflection.executor1r_before_request()
    assert reflection.synthetic_reflection_satisfies_authorization(request, issued.authorization) is False
    assert historical.validate_synthetic_runtime_authorization(old, spec=spec, source=source) is old


def test_provider_report_json_has_no_live_authorization_capability(issued, monkeypatch):
    historical_report = json.loads(json.dumps(issued.provider_outcome.as_dict()))
    monkeypatch.setattr(provider, "issue_pinned_java_exact_provider", lambda: historical_report)
    outcome = owner.issue_pinned_synthetic_runtime_authorization()
    assert outcome.status != owner.COMPLETE and outcome.authorization is None
    _assert_rejected(historical_report)


def test_provider_failure_closes_before_scenario_authorization(control, runtime_control):
    control.bind_version = "different-provider"
    outcome = owner.issue_pinned_synthetic_runtime_authorization()
    assert outcome.status != owner.COMPLETE and outcome.authorization is None
    assert runtime_control.commands == [] and runtime_control.sandbox_runs == 0


def test_missing_exact_frozen_source_stops_before_provider_issuance(runtime_control, monkeypatch):
    monkeypatch.setattr(historical, "get_executor1r_decrement_3_source", lambda: b"equivalent source is insufficient")
    monkeypatch.setattr(provider, "issue_pinned_java_exact_provider",
        lambda: pytest.fail("provider must not issue without recovered exact source"))
    with pytest.raises(ValueError):
        owner.issue_pinned_synthetic_runtime_authorization()
    assert runtime_control.commands == [] and runtime_control.sandbox_runs == 0


def test_wrong_process_cannot_validate_or_start_new_provider_proof(issued, runtime_control, monkeypatch):
    pid = issued.authorization.issuing_pid
    command_count = len(runtime_control.commands)
    monkeypatch.setattr(owner.os, "getpid", lambda: pid + 1)
    _assert_rejected(issued.authorization)
    try:
        outcome = owner.issue_pinned_synthetic_runtime_authorization()
    except ValueError:
        pass
    else:
        assert outcome.status != owner.COMPLETE and outcome.authorization is None
    assert len(runtime_control.commands) == command_count


def test_validation_calls_public_provider_validator_even_after_issuance(issued, monkeypatch):
    def denied(*args):
        raise ValueError("retained provider no longer authenticates")
    monkeypatch.setattr(provider, "validate_pinned_java_exact_provider", denied)
    _assert_rejected(issued.authorization)


def test_independent_hmac_domain_and_live_registry_are_required(issued, monkeypatch):
    monkeypatch.setattr(owner, "_SECRET", b"controlled-unrelated-hmac-key".ljust(32, b"!"))
    _assert_rejected(issued.authorization)


def test_removed_live_authorization_registry_cannot_be_reconstructed(issued):
    owner._LIVE.clear()
    _assert_rejected(issued.authorization)


def test_provider_live_registry_removal_invalidates_dependent_scope(issued):
    provider._LIVE.clear()
    _assert_rejected(issued.authorization)


def test_authorization_report_is_report_only_and_never_exports_hmac(issued):
    report = issued.authorization.as_dict()
    assert report["report_only"] is True
    assert report["synthetic_scenario_authorized"] is True
    assert all(report[field] is False for field in _FALSE_AUTHORITIES)
    assert '"_signature"' not in json.dumps(report)
    assert '"_signature"' not in json.dumps(issued.as_dict())
    _assert_rejected(report)
    json.dumps(issued.as_dict(), allow_nan=False)


def test_report_separates_provider_infrastructure_from_zero_synthetic_effects(issued):
    report = issued.as_dict()
    assert report["phase_id"] == owner.PHASE_ID
    assert report["schema_version"] == owner.SCHEMA_VERSION
    assert report["provider_proof_issuance_attempts"] == 1
    assert report["provider_exact_provider_proven"] is True
    assert report["provider_requirement_profile"] == "RUNTIME.JAVA.PINNED.1"
    assert report["provider_requirement_schema"] == "runtime_java_pinned_1_v1"
    assert all(value is False for value in report["provider_authority_false_matrix"].values())
    assert report["authorization_owner_local_effects"] == {
        "authorizations_issued": 1, "live_registry_entries_added": 1,
        "processes_created": 0, "containers_created": 0, "source_files_created": 0,
    }
    assert report["provider_proof_infrastructure_effects"]
    assert report["forbidden_effect_counts"] and all(type(count) is int and count == 0
        for count in report["forbidden_effect_counts"].values())
    assert set(report["forbidden_effect_counts"]) >= {
        "SyntheticStateBox", "reflection_reads", "runtime_lease_consumption",
        "reflection_lease_consumption", "EXECUTOR.1R", "BANK", "Apply",
        "repository_runtime_writes", "arbitrary_Java", "shell", "outbound_network", "host_mounts",
    }
    for flag in ("execution_lease_issued", "lifecycle_compatibility_evaluated", "lifecycle_execution_ready",
            "reflection_admission_issued", "SyntheticStateBox_executed", "authorization_scope_is_execution_lease",
            "provider_proof_consumed", "provider_proof_fallback"):
        assert report[flag] is False
    assert report["measured_observations"] is None
    assert report["remaining_phase_containers"] == 0
    assert report["cleanup_verified"] is True


def test_negative_matrix_is_reversible_and_performs_no_additional_provider_effects(issued, runtime_control):
    before = deepcopy(issued.as_dict())
    commands_before = deepcopy(runtime_control.commands)
    matrix = owner.negative_authentication_matrix(issued)
    assert matrix and all(type(value) is bool and value for value in matrix.values())
    assert issued.as_dict() == before
    assert runtime_control.commands == commands_before
    assert owner.validate_pinned_synthetic_runtime_authorization(issued.authorization) is issued.authorization


def test_issuance_and_validation_add_no_lifecycle_or_reflection_effects(runtime_control, monkeypatch):
    for module, names in (
        (lifecycle, ("issue_synthetic_runtime_execution_lease", "consume_synthetic_runtime_execution_lease")),
        (reflection, ("executor1r_before_request", "executor1r_after_request", "render_synthetic_read_only_reflection")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, lambda *args, **kwargs: pytest.fail("forbidden synthetic effect"))
    before = deepcopy((lifecycle._AUTHORIZATION_LEASES, lifecycle._LEASES))
    outcome = owner.issue_pinned_synthetic_runtime_authorization()
    assert outcome.status == owner.COMPLETE, outcome.reason
    assert owner.validate_pinned_synthetic_runtime_authorization(outcome.authorization) is outcome.authorization
    assert (lifecycle._AUTHORIZATION_LEASES, lifecycle._LEASES) == before
    assert runtime_control.sandbox_runs == 1
    assert all("SyntheticStateBox" not in repr(command) for command, _ in runtime_control.commands)
