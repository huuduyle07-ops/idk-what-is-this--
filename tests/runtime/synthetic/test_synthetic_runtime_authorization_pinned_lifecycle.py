"""Pure isolated-owner checks for SYNTH.AUTH.LIFECYCLE.PINNED.1.

The dependency seam is the public validator on a source-loaded test-only copy
of pinned authorization. It accepts exactly one inert public dataclass, never
an operational authorization or provider graph. Production validators and
registries remain unchanged. No positive consumption gate is invented.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, asdict, fields, replace
import gc
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from threading import Barrier, Thread
from types import SimpleNamespace
from weakref import ref

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core.runtime.synthetic import synthetic_runtime_authorization as old_authorization
    from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as old_lifecycle
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned as production_upstream
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned_lifecycle as production_owner
    from core.runtime.synthetic import synthetic_reflection_execution_lifecycle as reflection


ROOT = Path(__file__).resolve().parents[3]
OWNER_PATH = ROOT / "core/runtime/synthetic/synthetic_runtime_authorization_pinned_lifecycle.py"
UPSTREAM_PATH = ROOT / "core/runtime/synthetic/synthetic_runtime_authorization_pinned.py"
CONTRACT = json.loads((ROOT / "docs/roadmap/phases/"
    "SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1/contract.json").read_text(encoding="utf-8"))
API_NAMES = tuple(item["name"] for item in CONTRACT["public_api"]["operations"])
FALSE_AUTHORITY = tuple(CONTRACT["authority"]["false_in_all_states"])


@pytest.fixture(autouse=True)
def pure_scope():
    """Guard fixture construction as well as test bodies and keep old maps intact."""
    registries = (old_authorization._ISSUED_HANDLES,
        old_lifecycle._AUTHORIZATION_LEASES, old_lifecycle._LEASES,
        production_upstream._LIVE, production_upstream.provider_owner._LIVE,
        reflection._ADMISSION_LEASES, reflection._LEASES)
    baseline = tuple(dict(registry) for registry in registries)
    validator = production_upstream.validate_pinned_synthetic_runtime_authorization
    policy = old_lifecycle.CONSUMPTION_POLICY
    production_store = production_owner._STORE
    with no_runtime_effects(strict=True) as evidence:
        yield
    assert evidence.denied_attempts == {}
    assert tuple(dict(registry) for registry in registries) == baseline
    assert production_upstream.validate_pinned_synthetic_runtime_authorization is validator
    assert old_lifecycle.CONSUMPTION_POLICY == policy
    assert production_owner._STORE is production_store


def _source_module(name, path, marker):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(path.read_text(encoding="utf-8"), marker, "exec"), vars(module))
    return module


@pytest.fixture
def inert():
    names = ("_test_pinned_lifecycle_upstream", "_test_pinned_lifecycle_owner")
    upstream = _source_module(names[0], UPSTREAM_PATH,
        "<inert:pinned-lifecycle-tests:upstream>")
    owner = _source_module(names[1], OWNER_PATH,
        "<inert:pinned-lifecycle-tests:owner>")
    owner.authorization_owner = upstream
    scenario_values = {item.name: CONTRACT["scenario"][item.name]
        for item in fields(upstream.PinnedSyntheticScenarioIdentity)}
    scenario_values["arguments"] = tuple(scenario_values["arguments"])
    scenario_values["argument_types"] = tuple(scenario_values["argument_types"])
    scenario = upstream.PinnedSyntheticScenarioIdentity(**scenario_values)
    provenance, policy = CONTRACT["provider_provenance"], CONTRACT["activation_policy"]
    provider = upstream.PinnedSyntheticProviderIdentity(
        phase_id=provenance["root_phase_id"],
        schema_version=provenance["root_schema_version"],
        owner_identity=provenance["root_owner_identity"],
        proof_context_identity="1" * 64, receipt_id="2" * 64,
        fingerprint="3" * 64, evidence_digest="4" * 64,
        requirement_profile=policy["requirement_profile"],
        requirement_schema=policy["requirement_schema"],
        target_image_identity=upstream.REQUIREMENT.image_identity,
        runtime_sandbox_profile=policy["runtime_sandbox_profile"],
        runtime_sandbox_policy_sha256=policy["runtime_sandbox_policy_sha256"],
        controller_identity_evidence_json='{"inert":true}',
        cleanup_evidence_json='{"inert":true}', cleanup_evidence_digest="5" * 64)
    authorization = upstream.PinnedSyntheticRuntimeAuthorization(
        upstream.OWNER_ID, "a" * 64, "b" * 64, owner._ISSUER_PID,
        scenario, provider, "c" * 64)
    original_validator = upstream.validate_pinned_synthetic_runtime_authorization
    calls = []

    def validate(value, **kwargs):
        calls.append(value)
        if type(value) is not upstream.PinnedSyntheticRuntimeAuthorization or value is not authorization:
            raise upstream.PinnedSyntheticAuthorizationError(
                "pinned_synthetic_authorization_unauthenticated", "inert exact original required")
        return authorization

    upstream.validate_pinned_synthetic_runtime_authorization = validate
    try:
        yield SimpleNamespace(owner=owner, upstream=upstream, authorization=authorization,
            calls=calls, validate=validate, original_validator=original_validator)
    finally:
        for name in names:
            sys.modules.pop(name, None)


@contextmanager
def _edit(value, name, replacement):
    original = getattr(value, name)
    object.__setattr__(value, name, replacement)
    try:
        yield
    finally:
        object.__setattr__(value, name, original)


def _reject(inert, operation, code):
    with pytest.raises(inert.owner.PinnedSyntheticRuntimeExecutionLeaseError) as caught:
        operation()
    assert isinstance(caught.value, ValueError)
    assert caught.value.code == code
    assert type(caught.value.reason) is str and caught.value.reason
    return caught.value


def _lease(inert):
    return inert.owner.issue_pinned_synthetic_runtime_execution_lease(inert.authorization)


def _reads(inert, lease):
    owner, authorization = inert.owner, inert.authorization
    return (lambda: owner.validate_pinned_synthetic_runtime_execution_lease(lease, authorization),
        lambda: owner.pinned_synthetic_runtime_execution_lease_state(lease, authorization),
        lambda: owner.check_pinned_synthetic_runtime_execution_lease_preconditions(lease, authorization),
        lambda: owner.consume_pinned_synthetic_runtime_execution_lease(lease, authorization),
        lambda: owner.invalidate_pinned_synthetic_runtime_execution_lease(lease, authorization))


def _reconstruct(value, cls=None):
    return (cls or type(value))(**{item.name: getattr(value, item.name)
        for item in fields(value) if item.init})


def _clone(value, kind):
    if kind == "copy":
        return copy(value)
    if kind == "deepcopy":
        return deepcopy(value)
    if kind == "replace":
        return replace(value)
    if kind == "constructor":
        return _reconstruct(value)
    if kind == "JSON_constructor":
        payload = json.loads(json.dumps(asdict(value)))
        return type(value)(**{item.name: payload[item.name]
            for item in fields(value) if item.init})
    if kind == "JSON":
        return json.loads(json.dumps(asdict(value)))
    if kind == "report":
        return value.as_dict()
    if kind == "ID":
        return getattr(value, "lease_id", getattr(value, "authorization_id", None))
    if kind == "fingerprint":
        return value.fingerprint
    if kind == "wrapper":
        class Wrapper:
            def __getattr__(self, name):
                return getattr(value, name)
        return Wrapper()
    if kind == "subclass":
        class Subclass(type(value)):
            pass
        return _reconstruct(value, Subclass)
    if kind == "incomplete":
        return object.__new__(type(value))
    raise AssertionError(kind)


CLONE_KINDS = ("copy", "deepcopy", "replace", "constructor", "JSON_constructor",
    "JSON", "report", "ID", "fingerprint", "wrapper", "subclass", "incomplete")


def _consumed_history_fixture(inert, lease):
    """Install terminal *history* in the isolated module, without any transition.

    This tests signed terminal inspection only. It does not replace the consumer
    gate, exercise a successful consume, execute behavior or issue a provider.
    """
    owner = inert.owner
    record = owner._STORE.leases[lease.lease_id]
    consumed = replace(record, lifecycle_state=owner.CONSUMED,
        signature=owner._sign(record.projection_json, owner.CONSUMED))
    owner._STORE = replace(owner._STORE,
        leases={**owner._STORE.leases, lease.lease_id: consumed})


def test_distinct_owner_schema_type_and_exact_public_api(inert):
    owner = inert.owner
    assert (owner.OWNER_ID, owner.PHASE_ID, owner.SCHEMA_VERSION) == (
        "core.synthetic_runtime_authorization_pinned_lifecycle",
        "SYNTH.AUTH.LIFECYCLE.PINNED.1", "synthetic_runtime_execution_lease_pinned_1_v1")
    assert owner.PinnedSyntheticRuntimeExecutionLease.__name__ == "PinnedSyntheticRuntimeExecutionLease"
    assert not issubclass(owner.PinnedSyntheticRuntimeExecutionLease,
        old_lifecycle.SyntheticRuntimeExecutionLease)
    assert owner.PHASE_ID != old_lifecycle.PHASE_ID
    assert owner.SCHEMA_VERSION != old_lifecycle.SCHEMA_VERSION
    assert owner._SECRET is not old_lifecycle._SECRET
    assert owner._SECRET is not production_upstream._SECRET
    assert owner._LOCK is not old_lifecycle._LOCK
    assert all(callable(getattr(owner, name)) for name in API_NAMES)
    assert set((owner.ISSUED, owner.CONSUMED, owner.INVALIDATED)) == set(CONTRACT["state_machine"]["states"])
    assert set(owner.ERROR_CODES) == set(CONTRACT["error_taxonomy"])


def test_inert_seam_is_isolated_and_unauthenticated_in_production(inert):
    assert inert.upstream is not production_upstream
    assert inert.upstream._LIVE == {}
    assert inert.owner.authorization_owner is inert.upstream
    assert inert.upstream.PinnedSyntheticRuntimeAuthorization is not production_upstream.PinnedSyntheticRuntimeAuthorization
    with pytest.raises(production_upstream.PinnedSyntheticAuthorizationError):
        production_upstream.validate_pinned_synthetic_runtime_authorization(inert.authorization)
    with pytest.raises(inert.upstream.PinnedSyntheticAuthorizationError):
        inert.original_validator(inert.authorization)
    assert inert.validate(inert.authorization) is inert.authorization
    assert inert.owner._STORE.authorization_leases == inert.owner._STORE.leases == {}


def test_isolated_lease_cannot_escape_into_production_new_owner(inert):
    lease = _lease(inert)
    snapshot = production_owner._STORE
    assert inert.owner is not production_owner
    assert type(lease) is not production_owner.PinnedSyntheticRuntimeExecutionLease
    assert snapshot.authorization_leases == snapshot.leases == {}
    with pytest.raises(production_owner.PinnedSyntheticRuntimeExecutionLeaseError) as error:
        production_owner.validate_pinned_synthetic_runtime_execution_lease(lease)
    assert error.value.code == "LEASE_UNAUTHENTICATED"
    assert production_owner._STORE is snapshot


def test_issued_snapshot_binds_complete_original_public_projections_and_policy(inert):
    owner, authorization = inert.owner, inert.authorization
    before = asdict(authorization)
    lease = _lease(inert)
    assert type(lease) is owner.PinnedSyntheticRuntimeExecutionLease
    assert owner.validate_pinned_synthetic_runtime_execution_lease(lease) is lease
    assert owner.validate_pinned_synthetic_runtime_execution_lease(lease, authorization) is lease
    assert owner.pinned_synthetic_runtime_execution_lease_state(lease) == owner.ISSUED
    assert lease.lifecycle_state == owner.ISSUED
    assert lease.initial_state == owner.ISSUED
    assert lease.authorization_id == authorization.authorization_id
    assert lease.authorization_fingerprint == authorization.fingerprint
    assert lease.authorization_proof_context_id == authorization.proof_context_id
    assert lease.scenario is not authorization.scenario
    assert lease.provider is not authorization.provider
    assert type(lease.scenario) is type(authorization.scenario)
    assert type(lease.provider) is type(authorization.provider)
    assert asdict(lease.scenario) == asdict(authorization.scenario)
    assert asdict(lease.provider) == asdict(authorization.provider)
    assert set(asdict(lease.provider)) == set(CONTRACT["provider_provenance"]["projection_fields"])
    assert (lease.scenario_phase_id, lease.source_kind) == (
        CONTRACT["scenario"]["scenario_phase_id"], CONTRACT["scenario"]["source_kind"])
    assert lease.activation_policy_identity == CONTRACT["activation_policy"]["identity"]
    assert len(lease.activation_policy_digest) == 64
    assert asdict(authorization) == before
    record = owner._STORE.leases[lease.lease_id]
    assert record.authorization is authorization
    assert record.lease_ref() is lease


def test_issuance_accepts_only_original_authorization_without_provider_or_scenario_overrides(inert):
    owner = inert.owner
    for name, value in (("provider", inert.authorization.provider),
            ("scenario", inert.authorization.scenario), ("ready", True)):
        with pytest.raises(TypeError):
            owner.issue_pinned_synthetic_runtime_execution_lease(inert.authorization, **{name: value})
    assert owner._STORE.authorization_leases == owner._STORE.leases == {}


def test_every_public_operation_revalidates_exact_original_under_owner_lock(inert):
    owner, authorization = inert.owner, inert.authorization

    def locked_validate(candidate, **kwargs):
        assert owner._LOCK.locked()
        return inert.validate(candidate, **kwargs)

    inert.upstream.validate_pinned_synthetic_runtime_authorization = locked_validate
    lease = _lease(inert)
    for operation in _reads(inert, lease)[:-1]:
        inert.calls.clear()
        try:
            operation()
        except owner.PinnedSyntheticRuntimeExecutionLeaseError as error:
            assert error.code == "PROOF_UNRESOLVED"
        assert inert.calls and all(value is authorization for value in inert.calls)
    inert.calls.clear()
    owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)
    assert inert.calls and all(value is authorization for value in inert.calls)


@pytest.mark.parametrize("kind", CLONE_KINDS)
def test_authorization_copy_export_reconstruction_and_subclass_rejected(inert, kind):
    owner = inert.owner
    lease = _lease(inert)
    candidate = _clone(inert.authorization, kind)
    _reject(inert, lambda: owner.issue_pinned_synthetic_runtime_execution_lease(candidate),
        "PINNED_AUTH_UNAUTHENTICATED")
    for operation in (owner.validate_pinned_synthetic_runtime_execution_lease,
            owner.pinned_synthetic_runtime_execution_lease_state,
            owner.check_pinned_synthetic_runtime_execution_lease_preconditions,
            owner.consume_pinned_synthetic_runtime_execution_lease,
            owner.invalidate_pinned_synthetic_runtime_execution_lease):
        _reject(inert, lambda: operation(lease, candidate), "LEASE_UNAUTHENTICATED")
    assert owner.pinned_synthetic_runtime_execution_lease_state(lease) == owner.ISSUED


@pytest.mark.parametrize("state", ("ISSUED", "CONSUMED", "INVALIDATED"))
@pytest.mark.parametrize("kind", CLONE_KINDS)
def test_lease_copy_export_reconstruction_and_subclass_rejected(inert, state, kind):
    lease = _lease(inert)
    if state == "CONSUMED":
        _consumed_history_fixture(inert, lease)
    elif state == "INVALIDATED":
        inert.owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)
    candidate = _clone(lease, kind)
    for operation in _reads(inert, candidate):
        _reject(inert, operation, "LEASE_UNAUTHENTICATED")
    assert inert.owner.pinned_synthetic_runtime_execution_lease_state(lease) == state


def test_validator_cannot_substitute_equivalent_return_value(inert):
    candidate = copy(inert.authorization)
    inert.upstream.validate_pinned_synthetic_runtime_authorization = lambda value: candidate
    _reject(inert, lambda: _lease(inert), "PINNED_AUTH_UNAUTHENTICATED")
    assert inert.owner._STORE.authorization_leases == inert.owner._STORE.leases == {}


@pytest.mark.parametrize("name,value", (
    ("owner_identity", "core.synthetic_runtime_authorization"),
    ("phase_id", "SYNTH.AUTH.1"),
    ("schema_version", "synthetic_runtime_authorization_1_v1")))
def test_original_identity_cannot_relabel_old_authorization_epoch(inert, name, value):
    lease = _lease(inert)
    snapshot = inert.owner._STORE
    with _edit(inert.authorization, name, value):
        for operation in (lambda: _lease(inert), *_reads(inert, lease)):
            _reject(inert, operation, "PINNED_AUTH_SCOPE_MISMATCH")
            assert inert.owner._STORE is snapshot


@pytest.mark.parametrize("upstream_code,expected", (
    ("pinned_synthetic_authorization_unauthenticated", "PINNED_AUTH_UNAUTHENTICATED"),
    ("pinned_synthetic_authorization_scope_mismatch", "PINNED_AUTH_SCOPE_MISMATCH"),
    ("pinned_synthetic_provider_graph_mismatch", "PINNED_PROVIDER_PROVENANCE_MISMATCH"),
    ("pinned_provider_exact_requirement_required", "PINNED_PROVIDER_PROVENANCE_MISMATCH"),
    ("unknown_upstream_failure", "PROOF_UNRESOLVED")))
def test_upstream_failures_preserve_distinct_categories_and_original_evidence(inert, upstream_code, expected):
    lease = _lease(inert)

    def unavailable(value):
        raise inert.upstream.PinnedSyntheticAuthorizationError(upstream_code, "inert failure detail")

    inert.upstream.validate_pinned_synthetic_runtime_authorization = unavailable
    snapshot = inert.owner._STORE
    for operation in (lambda: _lease(inert), *_reads(inert, lease)):
        error = _reject(inert, operation, expected)
        assert error.upstream_code == upstream_code
        assert error.upstream_reason == "inert failure detail"
        assert inert.owner._STORE is snapshot


def test_unexpected_validator_error_is_unresolved_and_never_a_permissive_fallback(inert):
    lease = _lease(inert)

    def unexpected(value):
        raise RuntimeError("inert unexpected validator failure")

    inert.upstream.validate_pinned_synthetic_runtime_authorization = unexpected
    snapshot = inert.owner._STORE
    for operation in (lambda: _lease(inert), *_reads(inert, lease)):
        _reject(inert, operation, "PROOF_UNRESOLVED")
        assert inert.owner._STORE is snapshot


@pytest.mark.parametrize("location", ("authorization", "lease"))
def test_provider_projection_change_is_provenance_failure_on_every_operation(inert, location):
    lease = _lease(inert)
    provider = getattr(inert, location, None).provider if location == "authorization" else lease.provider
    for item in fields(provider):
        changed = replace(provider, **{item.name: "changed-inert-provenance"})
        target = inert.authorization if location == "authorization" else lease
        with _edit(target, "provider", changed):
            for operation in _reads(inert, lease):
                _reject(inert, operation, "PINNED_PROVIDER_PROVENANCE_MISMATCH")
        assert inert.owner.pinned_synthetic_runtime_execution_lease_state(lease) == "ISSUED"


@pytest.mark.parametrize("name,value", (
    ("scenario_id", "synthetic.other"), ("source_sha256", "f" * 64),
    ("source_size_bytes", 240), ("definition_sha256", "f" * 64),
    ("class_name", "OtherStateBox"), ("method_name", "increment"),
    ("method_signature", "int SyntheticStateBox.decrement(int)"),
    ("arguments", (4,)), ("argument_types", ("long",)), ("return_type", "int"),
    ("field_owner", "OtherStateBox"), ("field_name", "other"), ("field_type", "long"),
    ("expected_before", 11), ("expected_return", False), ("expected_after", 8),
    ("arguments", (3.0,)), ("arguments", (True,)), ("arguments", [3]),
    ("source_size_bytes", 239.0), ("expected_return", 1)))
def test_scenario_mismatch_and_primitive_aliases_are_scope_failures(inert, name, value):
    lease = _lease(inert)
    changed = replace(inert.authorization.scenario, **{name: value})
    for target in (inert.authorization, lease):
        with _edit(target, "scenario", changed):
            for operation in _reads(inert, lease):
                _reject(inert, operation, "PINNED_AUTH_SCOPE_MISMATCH")
    assert inert.owner.pinned_synthetic_runtime_execution_lease_state(lease) == "ISSUED"


@pytest.mark.parametrize("name", ("scenario_phase_id", "source_kind", "activation_policy_identity",
    "activation_policy_digest"))
def test_signed_lease_scope_and_policy_mutations_have_scope_category(inert, name):
    lease = _lease(inert)
    with _edit(lease, name, "changed-inert-scope"):
        for operation in _reads(inert, lease):
            _reject(inert, operation, "PINNED_AUTH_SCOPE_MISMATCH")


def test_every_other_public_issuance_field_is_authenticated(inert):
    lease = _lease(inert)
    semantic = {"scenario", "provider", "scenario_phase_id", "source_kind",
        "activation_policy_identity", "activation_policy_digest", "issuing_pid"}
    for item in fields(lease):
        if item.name in semantic:
            continue
        original = getattr(lease, item.name)
        altered = not original if type(original) is bool else "changed-inert-field"
        with _edit(lease, item.name, altered):
            _reject(inert, lambda: inert.owner.validate_pinned_synthetic_runtime_execution_lease(lease),
                "LEASE_UNAUTHENTICATED")
    assert lease.lifecycle_state == "ISSUED"


@pytest.mark.parametrize("name,value", (
    ("runtime_authority", 0), ("lease_issued", 1),
    ("one_shot_exact_synthetic_activation_capability", 1), ("issuing_pid", True)))
def test_equal_foreign_primitive_types_do_not_authenticate(inert, name, value):
    lease = _lease(inert)
    with _edit(lease, name, value):
        _reject(inert, lambda: inert.owner.validate_pinned_synthetic_runtime_execution_lease(lease),
            "LEASE_UNAUTHENTICATED")


def test_wrong_process_rejected_before_inherited_lock_without_launch(inert, monkeypatch):
    owner = inert.owner
    lease = _lease(inert)

    class InheritedLocked:
        def __enter__(self):
            pytest.fail("foreign process acquired an inherited owner lock")

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(owner, "os", SimpleNamespace(getpid=lambda: owner._ISSUER_PID + 1))
    monkeypatch.setattr(owner, "_LOCK", InheritedLocked())
    for operation in (lambda: _lease(inert), *_reads(inert, lease)):
        _reject(inert, operation, "LEASE_WRONG_PROCESS")


def test_wrong_lease_pid_is_rejected_before_lock(inert, monkeypatch):
    lease = _lease(inert)

    class ForbiddenLock:
        def __enter__(self):
            pytest.fail("wrong lease PID reached owner lock")

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(inert.owner, "_LOCK", ForbiddenLock())
    with _edit(lease, "issuing_pid", lease.issuing_pid + 1):
        for operation in _reads(inert, lease):
            _reject(inert, operation, "LEASE_WRONG_PROCESS")


def test_one_shot_key_uses_only_authenticated_upstream_fields_and_duplicate_is_permanent(inert):
    owner, authorization = inert.owner, inert.authorization
    lease = _lease(inert)
    key = (authorization.owner_identity, authorization.phase_id, authorization.schema_version,
        authorization.issuing_pid, authorization.authorization_id)
    assert owner._one_shot_key(authorization) == key
    assert owner._STORE.authorization_leases == {key: lease.lease_id}
    _reject(inert, lambda: _lease(inert), "DUPLICATE_LEASE_ISSUANCE")
    with _edit(authorization, "proof_context_id", "d" * 64):
        _reject(inert, lambda: _lease(inert), "DUPLICATE_LEASE_ISSUANCE")
    owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)
    _reject(inert, lambda: _lease(inert), "DUPLICATE_LEASE_ISSUANCE")
    assert owner._STORE.authorization_leases == {key: lease.lease_id}


@pytest.mark.parametrize("state", ("ISSUED", "CONSUMED", "INVALIDATED"))
def test_lease_collection_keeps_permanent_key_record_and_original_authorization(inert, state):
    owner = inert.owner
    lease = _lease(inert)
    if state == "CONSUMED":
        _consumed_history_fixture(inert, lease)
    elif state == "INVALIDATED":
        owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)
    lease_id, weak = lease.lease_id, ref(lease)
    del lease
    gc.collect()
    assert weak() is None
    assert owner._STORE.leases[lease_id].authorization is inert.authorization
    assert owner._STORE.leases[lease_id].lifecycle_state == state
    _reject(inert, lambda: _lease(inert), "DUPLICATE_LEASE_ISSUANCE")


def test_readiness_is_report_only_and_consumption_remains_unresolved(inert):
    owner, authorization = inert.owner, inert.authorization
    lease = _lease(inert)
    snapshot = owner._STORE
    readiness = owner.check_pinned_synthetic_runtime_execution_lease_preconditions(lease, authorization)
    assert readiness.lease_local_preconditions_satisfied is True
    assert readiness.behavioral_activation_ready is False
    assert readiness.current_state == owner.ISSUED
    assert readiness.reason == "PROOF_UNRESOLVED"
    assert readiness.report_only is True
    with pytest.raises((FrozenInstanceError, AttributeError)):
        readiness.behavioral_activation_ready = True
    _reject(inert, lambda: owner.consume_pinned_synthetic_runtime_execution_lease(lease, authorization),
        "PROOF_UNRESOLVED")
    assert owner._STORE is snapshot
    assert lease.lifecycle_state == owner.ISSUED
    assert lease.runtime_activation_consumed is False


@pytest.mark.parametrize("override", (True, {"ready": True}, {"behavioral_activation_ready": True}))
def test_caller_readiness_boolean_json_and_override_are_not_api_inputs(inert, override):
    owner, authorization = inert.owner, inert.authorization
    lease = _lease(inert)
    with pytest.raises(TypeError):
        owner.consume_pinned_synthetic_runtime_execution_lease(lease, authorization, override)
    for name in ("ready", "readiness", "consumer_readiness", "test_only_bypass"):
        with pytest.raises(TypeError):
            owner.consume_pinned_synthetic_runtime_execution_lease(lease, authorization, **{name: override})
    assert lease.lifecycle_state == "ISSUED"


@pytest.mark.parametrize("operation_name", ("check_pinned_synthetic_runtime_execution_lease_preconditions",
    "consume_pinned_synthetic_runtime_execution_lease"))
def test_readiness_and_consumption_require_supplied_exact_original_authorization(inert, operation_name):
    lease = _lease(inert)
    operation = getattr(inert.owner, operation_name)
    with pytest.raises(TypeError):
        operation(lease)
    _reject(inert, lambda: operation(lease, None), "LEASE_UNAUTHENTICATED")
    assert lease.lifecycle_state == "ISSUED"


@pytest.mark.parametrize("state,reason", (("CONSUMED", "LEASE_ALREADY_CONSUMED"),
    ("INVALIDATED", "LEASE_INVALIDATED")))
def test_terminal_history_is_inspectable_stable_and_does_not_grant_readiness(inert, state, reason):
    owner, authorization = inert.owner, inert.authorization
    lease = _lease(inert)
    fingerprint, original_fields = lease.fingerprint, asdict(lease)
    if state == "CONSUMED":
        _consumed_history_fixture(inert, lease)
    else:
        assert owner.invalidate_pinned_synthetic_runtime_execution_lease(lease) is lease
    snapshot = owner._STORE
    assert owner.validate_pinned_synthetic_runtime_execution_lease(lease, authorization) is lease
    assert owner.pinned_synthetic_runtime_execution_lease_state(lease) == state
    assert lease.fingerprint == fingerprint
    assert asdict(lease) == original_fields
    assert lease.runtime_activation_consumed is (state == "CONSUMED")
    readiness = owner.check_pinned_synthetic_runtime_execution_lease_preconditions(lease, authorization)
    assert readiness.lease_local_preconditions_satisfied is False
    assert readiness.behavioral_activation_ready is False
    assert readiness.current_state == state and readiness.reason == reason
    for operation in (owner.consume_pinned_synthetic_runtime_execution_lease,
            owner.invalidate_pinned_synthetic_runtime_execution_lease):
        error = _reject(inert, lambda: operation(lease, authorization), reason)
        assert error.category == "LEASE_NOT_ISSUED"
        assert owner._STORE is snapshot
    _reject(inert, lambda: _lease(inert), "DUPLICATE_LEASE_ISSUANCE")


@pytest.mark.parametrize("state", ("CONSUMED", "INVALIDATED", "UNKNOWN"))
def test_forged_or_unknown_private_state_cannot_authenticate(inert, state):
    owner = inert.owner
    lease = _lease(inert)
    original = owner._STORE
    record = original.leases[lease.lease_id]
    owner._STORE = replace(original,
        leases={lease.lease_id: replace(record, lifecycle_state=state)})
    for operation in _reads(inert, lease):
        _reject(inert, operation, "LEASE_UNAUTHENTICATED")
    owner._STORE = original
    assert lease.lifecycle_state == "ISSUED"


def test_terminal_state_does_not_survive_failed_upstream_authentication_as_a_success(inert):
    lease = _lease(inert)
    inert.owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)

    def gone(value):
        raise inert.upstream.PinnedSyntheticAuthorizationError("pinned_synthetic_authorization_unauthenticated")

    inert.upstream.validate_pinned_synthetic_runtime_authorization = gone
    for operation in _reads(inert, lease):
        _reject(inert, operation, "PINNED_AUTH_UNAUTHENTICATED")


@pytest.mark.parametrize("state", ("ISSUED", "CONSUMED", "INVALIDATED"))
def test_all_general_authority_flags_remain_false_and_export_omits_authentication_secrets(inert, state):
    lease = _lease(inert)
    if state == "CONSUMED":
        _consumed_history_fixture(inert, lease)
    elif state == "INVALIDATED":
        inert.owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)
    assert lease.lease_issued is True
    assert lease.one_shot_exact_synthetic_activation_capability is True
    assert all(getattr(lease, name) is False for name in FALSE_AUTHORITY)
    report = lease.as_dict()
    assert report["report_only"] is True
    assert report["current_state"] == state
    assert report["runtime_activation_consumed"] is (state == "CONSUMED")
    assert not any("signature" in name or "secret" in name or "registry" in name for name in report)
    assert inert.owner._STORE.leases[lease.lease_id].signature not in json.dumps(report)


def test_public_object_cannot_mutate_state_or_restore_a_terminal_lease(inert):
    owner = inert.owner
    lease = _lease(inert)
    for name in ("lifecycle_state", "runtime_activation_consumed"):
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            object.__setattr__(lease, name, "CONSUMED")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        lease.authorization_id = "different"
    owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)
    for target in (owner.ISSUED, "UNKNOWN"):
        _reject(inert, lambda: owner._transition(lease, inert.authorization, target), "LEASE_UNAUTHENTICATED")
    assert lease.lifecycle_state == owner.INVALIDATED
    assert not any(name.startswith(("reset_", "restore_", "refund_", "replay_")) for name in vars(owner))


def test_old_owner_and_pinned_owner_types_cannot_interchange_without_fabricating_old_handles(inert):
    lease = _lease(inert)
    # The unchanged old validator rejects the new exact original at its type gate.
    with pytest.raises(old_lifecycle.SyntheticRuntimeExecutionLeaseError):
        old_lifecycle.validate_synthetic_runtime_execution_lease(lease)
    _reject(inert, lambda: inert.owner.validate_pinned_synthetic_runtime_execution_lease(
        old_lifecycle.SyntheticRuntimeExecutionLease), "LEASE_UNAUTHENTICATED")
    tree = ast.parse(OWNER_PATH.read_text(encoding="utf-8"))
    assert any(isinstance(node, ast.Compare) and ast.unparse(node) ==
        "type(lease) is not PinnedSyntheticRuntimeExecutionLease" for node in ast.walk(tree))
    assert reflection.runtime_owner is old_lifecycle
    assert reflection.authorization_owner is old_authorization
    assert "synthetic_reflection" not in OWNER_PATH.read_text(encoding="utf-8")


def test_domain_roles_and_canonical_activation_policy_are_exact(inert):
    owner = inert.owner
    domain = CONTRACT["authentication_domain"]["domain"].encode("utf-8")
    assert owner._DOMAIN == domain
    policy = CONTRACT["activation_policy"]
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    expected = sha256(domain + b"\0activation-policy\0" + canonical).hexdigest()
    assert _lease(inert).activation_policy_digest == expected
    sample = {"z": [False, None, 3], "a": "identity"}
    expected_canonical = json.dumps(sample, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    digests = {owner._digest(sample, role) for role in CONTRACT["authentication_domain"]["roles"]}
    assert len(digests) == 4
    for role in CONTRACT["authentication_domain"]["roles"]:
        assert owner._digest(sample, role) == sha256(domain + b"\0" + role.encode() + b"\0" + expected_canonical).hexdigest()
    assert owner._sign("{}", owner.ISSUED) != owner._sign("{}", owner.INVALIDATED)


@pytest.mark.parametrize("value", (float("nan"), float("inf"), {1: "non-string-key"}, {"x": object()}))
def test_noncanonical_primitive_payloads_fail_closed(inert, value):
    with pytest.raises((inert.owner.PinnedSyntheticRuntimeExecutionLeaseError, ValueError, TypeError)):
        inert.owner._digest(value, "lease-evidence")


@pytest.mark.parametrize("failure", ("lease-evidence", "lease-fingerprint", "record-signing"))
def test_partial_issuance_failure_publishes_neither_record_nor_key(inert, monkeypatch, failure):
    owner = inert.owner
    snapshot = owner._STORE
    if failure == "record-signing":
        def fail(*args):
            raise RuntimeError("inert signing interruption")
        monkeypatch.setattr(owner, "_sign", fail)
    else:
        original = owner._digest

        def fail(value, role):
            if role == failure:
                raise RuntimeError("inert digest interruption")
            return original(value, role)
        monkeypatch.setattr(owner, "_digest", fail)
    with pytest.raises((RuntimeError, owner.PinnedSyntheticRuntimeExecutionLeaseError)):
        _lease(inert)
    assert owner._STORE is snapshot
    assert snapshot.authorization_leases == snapshot.leases == {}


def test_terminal_signing_failure_preserves_identical_issued_snapshot(inert, monkeypatch):
    owner = inert.owner
    lease = _lease(inert)
    snapshot = owner._STORE

    original = owner._sign
    terminal_attempts = []

    def fail(projection, state):
        if state == owner.INVALIDATED:
            terminal_attempts.append(state)
            raise RuntimeError("inert terminal signing interruption")
        return original(projection, state)

    monkeypatch.setattr(owner, "_sign", fail)
    with pytest.raises((RuntimeError, owner.PinnedSyntheticRuntimeExecutionLeaseError)):
        owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)
    assert owner._STORE is snapshot
    assert snapshot.leases[lease.lease_id].lifecycle_state == owner.ISSUED
    assert terminal_attempts == [owner.INVALIDATED]


def test_terminal_store_construction_failure_preserves_signed_prior_record(inert, monkeypatch):
    owner = inert.owner
    lease = _lease(inert)
    snapshot = owner._STORE
    terminal_attempts = []
    original = owner._sign

    def sign(projection, state):
        if state == owner.INVALIDATED:
            terminal_attempts.append(state)
        return original(projection, state)

    def interrupted(*args, **kwargs):
        raise RuntimeError("inert terminal store interruption")

    monkeypatch.setattr(owner, "_sign", sign)
    monkeypatch.setattr(owner, "_OwnerStore", interrupted)
    with pytest.raises((RuntimeError, owner.PinnedSyntheticRuntimeExecutionLeaseError)):
        owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)
    assert terminal_attempts == [owner.INVALIDATED]
    assert owner._STORE is snapshot
    assert owner.pinned_synthetic_runtime_execution_lease_state(lease) == owner.ISSUED


@pytest.mark.parametrize("value", (None, True, 42, "", "G" * 64, "a" * 63))
def test_malformed_owner_generated_identifier_publishes_nothing(inert, monkeypatch, value):
    owner = inert.owner
    snapshot = owner._STORE
    monkeypatch.setattr(owner, "secrets", SimpleNamespace(token_hex=lambda size: value))
    _reject(inert, lambda: _lease(inert), "PROOF_UNRESOLVED")
    assert owner._STORE is snapshot
    assert snapshot.authorization_leases == snapshot.leases == {}


@pytest.mark.parametrize("component", ("_unsigned_lease", "_LeaseRecord", "_OwnerStore", "ref"))
def test_issuance_construction_exception_has_no_partial_publication(inert, monkeypatch, component):
    owner = inert.owner
    snapshot = owner._STORE

    def interrupted(*args, **kwargs):
        raise RuntimeError("inert constructor interruption")

    monkeypatch.setattr(owner, component, interrupted)
    with pytest.raises((RuntimeError, owner.PinnedSyntheticRuntimeExecutionLeaseError)):
        _lease(inert)
    assert owner._STORE is snapshot
    assert snapshot.authorization_leases == snapshot.leases == {}


def test_secret_or_record_signature_change_cannot_authenticate(inert, monkeypatch):
    owner = inert.owner
    lease = _lease(inert)
    monkeypatch.setattr(owner, "_SECRET", b"isolated-different-secret".ljust(32, b"!"))
    for operation in _reads(inert, lease):
        _reject(inert, operation, "LEASE_UNAUTHENTICATED")


def _race(operations):
    barrier = Barrier(len(operations))
    outcomes = []

    def run(operation):
        try:
            barrier.wait(timeout=5)
            outcomes.append(("success", operation()))
        except BaseException as error:
            outcomes.append(("error", error))

    threads = [Thread(target=run, args=(operation,)) for operation in operations]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert len(outcomes) == len(operations)
    return outcomes


def test_concurrent_duplicate_issuance_has_exactly_one_logical_commit(inert):
    owner = inert.owner
    outcomes = _race((lambda: _lease(inert), lambda: _lease(inert)))
    successes = [value for result, value in outcomes if result == "success"]
    errors = [value for result, value in outcomes if result == "error"]
    assert len(successes) == len(errors) == 1
    assert type(errors[0]) is owner.PinnedSyntheticRuntimeExecutionLeaseError
    assert errors[0].code == "DUPLICATE_LEASE_ISSUANCE"
    assert len(owner._STORE.leases) == len(owner._STORE.authorization_leases) == 1
    assert owner.validate_pinned_synthetic_runtime_execution_lease(successes[0]) is successes[0]


def test_consume_invalidate_race_commits_only_invalidation_with_unresolved_consumer(inert, monkeypatch):
    owner, authorization = inert.owner, inert.authorization
    lease = _lease(inert)
    signed_states = []
    original = owner._sign
    original_store = owner._OwnerStore
    publications = []

    def record_signing(projection, state):
        signed_states.append(state)
        return original(projection, state)

    def terminal_store(*args, **kwargs):
        store = original_store(*args, **kwargs)
        publications.append(store)
        return store

    monkeypatch.setattr(owner, "_sign", record_signing)
    monkeypatch.setattr(owner, "_OwnerStore", terminal_store)
    outcomes = _race((lambda: owner.consume_pinned_synthetic_runtime_execution_lease(lease, authorization),
        lambda: owner.invalidate_pinned_synthetic_runtime_execution_lease(lease, authorization)))
    assert sum(result == "success" for result, _ in outcomes) == 1
    errors = [value for result, value in outcomes if result == "error"]
    assert len(errors) == 1 and errors[0].code in ("PROOF_UNRESOLVED", "LEASE_INVALIDATED")
    assert owner.pinned_synthetic_runtime_execution_lease_state(lease) == owner.INVALIDATED
    assert len(publications) == 1
    assert owner._STORE is publications[0]
    assert publications[0].leases[lease.lease_id].lifecycle_state == owner.INVALIDATED
    assert owner.CONSUMED not in signed_states
    assert len(owner._STORE.leases) == len(owner._STORE.authorization_leases) == 1
    assert lease.runtime_activation_consumed is False


def test_two_invalidations_race_for_one_terminal_commit(inert):
    owner = inert.owner
    lease = _lease(inert)
    outcomes = _race((lambda: owner.invalidate_pinned_synthetic_runtime_execution_lease(lease),
        lambda: owner.invalidate_pinned_synthetic_runtime_execution_lease(lease)))
    assert sum(result == "success" for result, _ in outcomes) == 1
    errors = [value for result, value in outcomes if result == "error"]
    assert len(errors) == 1 and errors[0].code == "LEASE_INVALIDATED"
    assert lease.lifecycle_state == owner.INVALIDATED


def test_owner_has_no_provider_issuer_private_upstream_registry_or_old_signing_bridge():
    source = OWNER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert not any("issue_pinned_java" in name or "issue_pinned_synthetic_runtime_authorization" in name
        for name in calls)
    assert "authorization_owner.validate_pinned_synthetic_runtime_authorization" in calls
    assert not any(name.startswith("authorization_owner._") for name in calls)
    assert "authorization_owner._LIVE" not in source
    assert "synthetic_runtime_authorization_lifecycle" not in source
    assert not any(name in calls for name in ("subprocess.run", "subprocess.Popen", "os.system"))
