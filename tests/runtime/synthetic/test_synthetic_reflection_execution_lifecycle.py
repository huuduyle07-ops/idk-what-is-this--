"""Pure reflection lifecycle schedules, authentication and zero-effect proof."""
from contextlib import contextmanager
import copy
from dataclasses import fields, replace
import gc
from itertools import permutations
import json
from types import SimpleNamespace
from unittest.mock import patch
from weakref import ref

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core.runtime.synthetic import synthetic_reflection_execution_lifecycle as owner

auth_owner = owner.authorization_owner
runtime_owner = owner.runtime_owner
request_owner = owner.request_owner
admission_owner = owner.admission_owner
TEST_ONLY_RUNTIME_CONSUMPTIONS = []
TEST_ONLY_REFLECTION_CONSUMPTIONS = []


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


def _activation():
    auth = auth_owner.issue_synthetic_runtime_authorization(auth_owner.executor1r_decrement_3_spec(),
        source=auth_owner.get_executor1r_decrement_3_source())
    runtime = runtime_owner.issue_synthetic_runtime_execution_lease(auth)
    return auth, runtime


def _inputs(auth, runtime, role):
    request = (request_owner.executor1r_before_request() if role == owner.BEFORE_ROLE
        else request_owner.executor1r_after_request())
    admission = admission_owner.issue_synthetic_reflection_execution_admission(auth, request)
    return admission, request, runtime, auth


def _issue(inputs, role):
    return owner.issue_synthetic_reflection_execution_lease(*inputs, observation_role=role)


def _pair(role=owner.BEFORE_ROLE):
    inputs = _inputs(*_activation(), role)
    return _issue(inputs, role), inputs


def _activate(inputs):
    _, _, runtime, auth = inputs
    result = runtime_owner.consume_synthetic_runtime_execution_lease(runtime, auth)
    TEST_ONLY_RUNTIME_CONSUMPTIONS.append(runtime.lease_id)
    return result


def _consume(lease, inputs, role):
    result = owner.consume_synthetic_reflection_execution_lease(lease, *inputs, observation_role=role)
    TEST_ONLY_REFLECTION_CONSUMPTIONS.append(lease.lease_id)
    return result


def _ready(lease, inputs, role):
    return owner.synthetic_reflection_execution_lease_satisfies_executor(lease, *inputs, observation_role=role)


def _active(lease, inputs, role):
    return owner.consumable_during_active_execution(lease, *inputs, observation_role=role)


def _invalidate(lease, inputs, role):
    return owner.invalidate_synthetic_reflection_execution_lease(lease, *inputs, observation_role=role)


def _reject(operation, code=None):
    with pytest.raises(owner.SyntheticReflectionExecutionLeaseError) as caught:
        operation()
    if code:
        assert caught.value.code == code
    return caught.value.code


@contextmanager
def _set(obj, name, value):
    previous = getattr(obj, name)
    object.__setattr__(obj, name, value)
    try:
        yield
    finally:
        object.__setattr__(obj, name, previous)


def _different(value):
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    return value + "_tampered"


def test_two_exact_scopes_share_one_runtime_and_authorization():
    handles, report = owner.verify()
    auth, runtime = handles["authorization"], handles["runtime"]
    assert report["supported_lifecycle_scope_count"] == 2
    assert runtime.lifecycle_state == owner.ISSUED
    for label, role in (("before", owner.BEFORE_ROLE), ("after", owner.AFTER_ROLE)):
        lease = handles[label + "_lease"]
        assert owner.validate_synthetic_reflection_execution_lease(lease) is lease
        assert lease.runtime_execution_lease_id == lease.scenario_execution_lease_id == runtime.lease_id
        assert lease.runtime_execution_lease_fingerprint == runtime.fingerprint
        assert lease.upstream_authorization_issuance_id == auth.issuance_id
        assert lease.upstream_authorization_fingerprint == auth.fingerprint
        assert lease.reflection_request_issuance_id == handles[label + "_request"].issuance_id
        assert lease.reflection_admission_id == handles[label + "_admission"].admission_id
        assert (lease.owner, lease.member, lease.declared_type, lease.operation, lease.observation_role) == (
            "SyntheticStateBox", "value", "int", "read_exact_bound_field", role)
        assert lease.source_sha256 == runtime.source_sha256 == owner.SOURCE_SHA256
        assert lease.definition_sha256 == owner.DEFINITION_SHA256
        assert lease.schema_version == owner.SCHEMA_VERSION and lease.issuer_phase_id == owner.PHASE_ID
        assert lease.synthetic_reflection_execution_lease is True
        for item in fields(lease):
            if item.name.endswith("_authority"):
                assert getattr(lease, item.name) is False


@pytest.mark.parametrize("role", owner.SUPPORTED_ROLES)
def test_consumption_requires_active_exact_runtime_and_never_changes_upstreams(role):
    lease, inputs = _pair(role)
    admission, request, runtime, auth = inputs
    frozen_before = (auth.as_dict(), request.as_dict(), admission.as_dict())
    fingerprint, issuance = lease.fingerprint, lease.as_dict()
    assert _ready(lease, inputs, role) and not _active(lease, inputs, role)
    _reject(lambda: _consume(lease, inputs, role), "synthetic_reflection_lease_runtime_not_consumed")
    assert runtime.lifecycle_state == lease.lifecycle_state == owner.ISSUED
    _activate(inputs)
    runtime_before = runtime.as_dict()
    assert not _ready(lease, inputs, role) and _active(lease, inputs, role)
    assert _consume(lease, inputs, role) is lease
    assert lease.lifecycle_state == owner.CONSUMED
    assert owner.validate_synthetic_reflection_execution_lease(lease) is lease
    assert lease.fingerprint == fingerprint
    assert lease.as_dict() == {**issuance, "lifecycle_state": owner.CONSUMED}
    assert frozen_before == (auth.as_dict(), request.as_dict(), admission.as_dict())
    assert runtime_before == runtime.as_dict()
    assert not _active(lease, inputs, role)
    _reject(lambda: _consume(lease, inputs, role), "synthetic_reflection_lease_not_issued")
    _reject(lambda: _invalidate(lease, inputs, role), "synthetic_reflection_lease_not_issued")
    _reject(lambda: _issue(inputs, role), "synthetic_reflection_admission_already_leased")


def test_before_and_after_are_independent_effects_in_same_test_activation():
    auth, runtime = _activation()
    before_inputs, after_inputs = [_inputs(auth, runtime, role) for role in owner.SUPPORTED_ROLES]
    before, after = [_issue(inputs, role) for inputs, role in zip((before_inputs, after_inputs), owner.SUPPORTED_ROLES)]
    _activate(before_inputs)
    _consume(before, before_inputs, owner.BEFORE_ROLE)
    assert after.lifecycle_state == owner.ISSUED and _active(after, after_inputs, owner.AFTER_ROLE)
    _consume(after, after_inputs, owner.AFTER_ROLE)
    assert runtime.lifecycle_state == before.lifecycle_state == after.lifecycle_state == owner.CONSUMED


@pytest.mark.parametrize("role", owner.SUPPORTED_ROLES)
@pytest.mark.parametrize("runtime_state", (owner.ISSUED, owner.CONSUMED, owner.INVALIDATED))
def test_invalidation_is_terminal_and_never_spends_runtime(role, runtime_state):
    lease, inputs = _pair(role)
    if runtime_state == owner.CONSUMED:
        _activate(inputs)
    elif runtime_state == owner.INVALIDATED:
        runtime_owner.invalidate_synthetic_runtime_execution_lease(inputs[2], inputs[3])
    assert _invalidate(lease, inputs, role) is lease
    assert lease.lifecycle_state == owner.INVALIDATED
    assert inputs[2].lifecycle_state == runtime_state
    assert not _ready(lease, inputs, role) and not _active(lease, inputs, role)
    _reject(lambda: _consume(lease, inputs, role))
    _reject(lambda: _invalidate(lease, inputs, role))
    _reject(lambda: _issue(inputs, role), "synthetic_reflection_admission_already_leased")


@pytest.mark.parametrize("role", owner.SUPPORTED_ROLES)
@pytest.mark.parametrize("state", (owner.ISSUED, owner.CONSUMED, owner.INVALIDATED))
def test_duplicate_issuance_remains_blocked_after_collection(role, state):
    lease, inputs = _pair(role)
    if state == owner.CONSUMED:
        _activate(inputs)
        _consume(lease, inputs, role)
    elif state == owner.INVALIDATED:
        _invalidate(lease, inputs, role)
    weak = ref(lease)
    del lease
    gc.collect()
    assert weak() is None
    _reject(lambda: _issue(inputs, role), "synthetic_reflection_admission_already_leased")


@pytest.mark.parametrize("state", (owner.CONSUMED, owner.INVALIDATED))
def test_issuance_rejects_nonissued_runtime_without_burning_admission(state):
    inputs = _inputs(*_activation(), owner.BEFORE_ROLE)
    if state == owner.CONSUMED:
        _activate(inputs)
    else:
        runtime_owner.invalidate_synthetic_runtime_execution_lease(inputs[2], inputs[3])
    _reject(lambda: _issue(inputs, owner.BEFORE_ROLE), "synthetic_reflection_lease_runtime_not_issued")
    assert inputs[0].admission_id not in owner._ADMISSION_LEASES


@pytest.mark.parametrize("role", owner.SUPPORTED_ROLES)
def test_opposite_role_cannot_issue_precheck_consume_or_invalidate(role):
    lease, inputs = _pair(role)
    other = owner.AFTER_ROLE if role == owner.BEFORE_ROLE else owner.BEFORE_ROLE
    _reject(lambda: _issue(inputs, other))
    assert not _ready(lease, inputs, other)
    _activate(inputs)
    assert not _active(lease, inputs, other)
    _reject(lambda: _consume(lease, inputs, other))
    _reject(lambda: _invalidate(lease, inputs, other))
    assert lease.lifecycle_state == owner.ISSUED


@pytest.mark.parametrize("role", ("direct_public_return", "BEFORE", "AFTER", "BANK", "", None, True))
def test_no_generic_role(role):
    lease, inputs = _pair()
    _reject(lambda: _issue(inputs, role))
    _reject(lambda: _consume(lease, inputs, role))
    assert not _ready(lease, inputs, role)


def _reconstruct(value):
    return type(value)(**{f.name: getattr(value, f.name) for f in fields(value) if f.init})


def _json_reconstruct(value):
    payload = json.loads(json.dumps(value.as_dict()))
    return type(value)(**{f.name: payload.get(f.name, getattr(value, f.name)) for f in fields(value) if f.init})


CLONES = (copy.copy, copy.deepcopy, replace, _reconstruct, _json_reconstruct,
    lambda value: value.as_dict(), lambda value: json.loads(json.dumps(value.as_dict())),
    lambda value: value.fingerprint, lambda value: SimpleNamespace(**value.as_dict()),
    lambda value: getattr(value, "issuance_id", getattr(value, "admission_id", getattr(value, "lease_id", None))))


@pytest.mark.parametrize("index", range(4), ids=("admission", "request", "runtime", "authorization"))
@pytest.mark.parametrize("clone", CLONES)
def test_copied_or_reconstructed_upstream_cannot_issue_or_consume(index, clone):
    lease, inputs = _pair()
    altered = list(inputs)
    altered[index] = clone(inputs[index])
    _reject(lambda: _issue(altered, owner.BEFORE_ROLE))
    assert not _ready(lease, altered, owner.BEFORE_ROLE)
    _activate(inputs)
    _reject(lambda: _consume(lease, altered, owner.BEFORE_ROLE))
    assert not _active(lease, altered, owner.BEFORE_ROLE)
    assert lease.lifecycle_state == owner.ISSUED


@pytest.mark.parametrize("state", (owner.ISSUED, owner.CONSUMED, owner.INVALIDATED))
@pytest.mark.parametrize("clone", CLONES)
def test_copied_or_exported_lease_is_never_authority(state, clone):
    lease, inputs = _pair()
    if state == owner.CONSUMED:
        _activate(inputs)
        _consume(lease, inputs, owner.BEFORE_ROLE)
    elif state == owner.INVALIDATED:
        _invalidate(lease, inputs, owner.BEFORE_ROLE)
    value = clone(lease)
    _reject(lambda: owner.validate_synthetic_reflection_execution_lease(value))
    _reject(lambda: _consume(value, inputs, owner.BEFORE_ROLE))
    assert not _ready(value, inputs, owner.BEFORE_ROLE)
    assert not _active(value, inputs, owner.BEFORE_ROLE)
    assert lease.lifecycle_state == state


@pytest.mark.parametrize("index", range(4), ids=("admission", "request", "runtime", "authorization"))
def test_wrong_live_upstream_or_unrelated_consumed_runtime_rejected(index):
    lease, inputs = _pair()
    foreign, other_inputs = _pair()
    _activate(inputs)
    _activate(other_inputs)
    altered = list(inputs)
    altered[index] = other_inputs[index]
    _reject(lambda: _issue(altered, owner.BEFORE_ROLE))
    _reject(lambda: _consume(lease, altered, owner.BEFORE_ROLE))
    assert not _active(lease, altered, owner.BEFORE_ROLE)
    assert lease.lifecycle_state == foreign.lifecycle_state == owner.ISSUED


def test_wrong_request_and_admission_from_same_activation_rejected():
    lease, inputs = _pair()
    other = _inputs(inputs[3], inputs[2], owner.BEFORE_ROLE)
    _reject(lambda: _issue((inputs[0], other[1], *inputs[2:]), owner.BEFORE_ROLE))
    _reject(lambda: _issue((other[0], inputs[1], *inputs[2:]), owner.BEFORE_ROLE))
    _activate(inputs)
    _reject(lambda: _consume(lease, other, owner.BEFORE_ROLE))


def test_role_cross_use_of_other_live_read_in_same_activation_rejected():
    auth, runtime = _activation()
    before_inputs = _inputs(auth, runtime, owner.BEFORE_ROLE)
    after_inputs = _inputs(auth, runtime, owner.AFTER_ROLE)
    before, after = _issue(before_inputs, owner.BEFORE_ROLE), _issue(after_inputs, owner.AFTER_ROLE)
    _activate(before_inputs)
    for lease, inputs, role in ((before, after_inputs, owner.AFTER_ROLE), (after, before_inputs, owner.BEFORE_ROLE)):
        _reject(lambda: _consume(lease, inputs, role))
        assert not _active(lease, inputs, role)
    assert before.lifecycle_state == after.lifecycle_state == owner.ISSUED


@pytest.mark.parametrize("kind", ("subclass", "wrapper", "missing_fields"))
def test_foreign_or_incomplete_typed_lease_is_rejected(kind):
    lease, inputs = _pair()

    class Subclass(owner.SyntheticReflectionExecutionLease):
        pass

    class Wrapper:
        def __getattr__(self, name):
            return getattr(lease, name)

    if kind == "subclass":
        value = Subclass(**{f.name: getattr(lease, f.name) for f in fields(lease) if f.init})
    elif kind == "wrapper":
        value = Wrapper()
    else:
        value = object.__new__(owner.SyntheticReflectionExecutionLease)
    _reject(lambda: owner.validate_synthetic_reflection_execution_lease(value))
    _reject(lambda: _consume(value, inputs, owner.BEFORE_ROLE))
    assert not _ready(value, inputs, owner.BEFORE_ROLE)


@pytest.mark.parametrize("failure", ("reflection", "invocation", "protocol", "timeout", "cleanup"))
def test_later_failure_never_refunds_reflection_effect(failure):
    lease, inputs = _pair()
    _activate(inputs)
    _consume(lease, inputs, owner.BEFORE_ROLE)
    try:
        raise RuntimeError("test-only subsequent failure: " + failure)
    except RuntimeError:
        pass
    assert lease.lifecycle_state == owner.CONSUMED
    _reject(lambda: _consume(lease, inputs, owner.BEFORE_ROLE))
    _reject(lambda: _issue(inputs, owner.BEFORE_ROLE))


@pytest.mark.parametrize("name", tuple(f.name for f in fields(owner.SyntheticReflectionExecutionLease)))
def test_every_live_lease_field_is_authenticated(name):
    lease, inputs = _pair()
    with _set(lease, name, _different(getattr(lease, name))):
        _reject(lambda: owner.validate_synthetic_reflection_execution_lease(lease))
        _reject(lambda: _consume(lease, inputs, owner.BEFORE_ROLE))
        assert not _ready(lease, inputs, owner.BEFORE_ROLE)
    assert lease.lifecycle_state == owner.ISSUED


@pytest.mark.parametrize("index,name", ((0, "scenario_phase_id"), (0, "scenario_id"),
    (0, "source_sha256"), (0, "definition_sha256"), (0, "owner"), (0, "member"),
    (0, "declared_type"), (0, "operation"), (0, "observation_role"),
    (1, "phase_id"), (1, "definition_sha256"), (1, "declared_type"), (2, "source_sha256"),
    (3, "scenario_id")))
def test_live_upstream_scope_tampering_is_rejected_by_public_owner(index, name):
    lease, inputs = _pair()
    with _set(inputs[index], name, _different(getattr(inputs[index], name))):
        _reject(lambda: _issue(inputs, owner.BEFORE_ROLE))
        _reject(lambda: _consume(lease, inputs, owner.BEFORE_ROLE))
        assert not _ready(lease, inputs, owner.BEFORE_ROLE)


@pytest.mark.parametrize("name,value", (("issuing_process_id", True), ("runtime_authority", 0),
    ("synthetic_reflection_execution_lease", 1), ("declared_type", int), ("observation_role", [])))
def test_equal_or_foreign_primitive_types_fail_closed(name, value):
    lease, inputs = _pair()
    with _set(lease, name, value):
        _reject(lambda: owner.validate_synthetic_reflection_execution_lease(lease))
        assert not _ready(lease, inputs, owner.BEFORE_ROLE)


@pytest.mark.parametrize("module", (auth_owner, runtime_owner, request_owner, admission_owner, owner))
def test_independent_key_changes_reject_live_capabilities(safe_patch, module):
    lease, inputs = _pair()
    _activate(inputs)
    safe_patch.setattr(module, "_SECRET", b"changed-domain-key".ljust(32, b"!"))
    _reject(lambda: owner.validate_synthetic_reflection_execution_lease(lease))
    _reject(lambda: _consume(lease, inputs, owner.BEFORE_ROLE))
    assert not _ready(lease, inputs, owner.BEFORE_ROLE)
    assert not _active(lease, inputs, owner.BEFORE_ROLE)
    _reject(lambda: _issue(inputs, owner.BEFORE_ROLE))


def test_separate_hmac_domain_and_retained_upstream_identities():
    assert len({module._SECRET for module in (auth_owner, runtime_owner, request_owner, admission_owner, owner)}) == 5
    lease, inputs = _pair()
    refs = [ref(value) for value in inputs]
    del inputs
    gc.collect()
    assert all(weak() is not None for weak in refs)
    assert owner.validate_synthetic_reflection_execution_lease(lease) is lease


def test_foreign_process_rejected_before_inherited_lock(safe_patch):
    lease, inputs = _pair()

    class InheritedLocked:
        def __enter__(self):
            raise AssertionError("foreign process waited on inherited lock")

        def __exit__(self, *args):
            pass

    safe_patch.setattr(owner.os, "getpid", lambda: lease.issuing_process_id + 1)
    safe_patch.setattr(owner, "_LOCK", InheritedLocked())
    for operation in (lambda: _issue(inputs, owner.BEFORE_ROLE),
            lambda: owner.validate_synthetic_reflection_execution_lease(lease),
            lambda: _consume(lease, inputs, owner.BEFORE_ROLE),
            lambda: _invalidate(lease, inputs, owner.BEFORE_ROLE)):
        _reject(operation)
    assert not _ready(lease, inputs, owner.BEFORE_ROLE)
    assert not _active(lease, inputs, owner.BEFORE_ROLE)


@pytest.mark.parametrize("state", (owner.CONSUMED, owner.INVALIDATED, "UNKNOWN", owner.ISSUED))
def test_forged_private_state_cannot_reset_or_consume(safe_patch, state):
    lease, inputs = _pair()
    if state == owner.ISSUED:
        _activate(inputs)
        _consume(lease, inputs, owner.BEFORE_ROLE)
    record = owner._LEASES[lease.lease_id]
    with safe_patch.context() as edit:
        edit.setitem(owner._LEASES, lease.lease_id, replace(record, lifecycle_state=state))
        _reject(lambda: owner.validate_synthetic_reflection_execution_lease(lease))
        _reject(lambda: _consume(lease, inputs, owner.BEFORE_ROLE))
        assert not _active(lease, inputs, owner.BEFORE_ROLE)
    assert lease.lifecycle_state == record.lifecycle_state


def test_closed_transitions_and_no_persistence_or_refund_api():
    lease, inputs = _pair()
    for state in (owner.ISSUED, "UNKNOWN"):
        _reject(lambda: owner._transition(lease, *inputs, owner.BEFORE_ROLE, state),
            "synthetic_reflection_lease_transition_forbidden")
    for name in ("reset", "refund", "restore", "persist", "reissue"):
        assert not any(public.startswith(name) for public in dir(owner) if not public.startswith("_"))
    with pytest.raises((AttributeError, TypeError)):
        object.__setattr__(lease, "lifecycle_state", owner.CONSUMED)
    payload = json.dumps(lease.as_dict())
    assert "signature" not in payload and "secret" not in payload


_SCHEDULES = tuple(order for order in permutations(("check_a", "check_b", "consume_a", "consume_b"))
    if order.index("check_a") < order.index("consume_a") and order.index("check_b") < order.index("consume_b"))


@pytest.mark.parametrize("role", owner.SUPPORTED_ROLES)
@pytest.mark.parametrize("order", _SCHEDULES)
def test_two_callers_with_stale_prechecks_have_exactly_one_transition(role, order):
    lease, inputs = _pair(role)
    _activate(inputs)
    successes, failures = 0, 0
    for step in order:
        if step.startswith("check"):
            assert _active(lease, inputs, role) == (successes == 0)
        else:
            try:
                _consume(lease, inputs, role)
                successes += 1
            except owner.SyntheticReflectionExecutionLeaseError as error:
                assert error.code == "synthetic_reflection_lease_not_issued"
                failures += 1
    assert successes == failures == 1


@pytest.mark.parametrize("first", ("consume", "invalidate"))
def test_consume_and_invalidate_compete_for_one_terminal_transition(first):
    lease, inputs = _pair()
    _activate(inputs)
    if first == "consume":
        _consume(lease, inputs, owner.BEFORE_ROLE)
        _reject(lambda: _invalidate(lease, inputs, owner.BEFORE_ROLE))
    else:
        _invalidate(lease, inputs, owner.BEFORE_ROLE)
        _reject(lambda: _consume(lease, inputs, owner.BEFORE_ROLE))


def test_authentication_signing_and_commits_share_one_real_lock(safe_patch):
    events = []
    authenticate, sign = owner._authenticate_inputs, owner._sign

    def checked_authenticate(*args):
        assert owner._LOCK.locked()
        events.append("authenticate")
        return authenticate(*args)

    def checked_sign(*args):
        assert owner._LOCK.locked()
        events.append("sign")
        return sign(*args)

    class RecordingRegistry(dict):
        def __setitem__(self, key, value):
            assert owner._LOCK.locked()
            events.append(value.lifecycle_state)
            return super().__setitem__(key, value)

    safe_patch.setattr(owner, "_authenticate_inputs", checked_authenticate)
    safe_patch.setattr(owner, "_sign", checked_sign)
    safe_patch.setattr(owner, "_LEASES", RecordingRegistry(owner._LEASES))
    lease, inputs = _pair()
    _activate(inputs)
    _consume(lease, inputs, owner.BEFORE_ROLE)
    assert [event for event in events if event in (owner.ISSUED, owner.CONSUMED)] == [owner.ISSUED, owner.CONSUMED]
    assert not owner._LOCK.locked()


def test_all_four_public_owner_validators_are_called(safe_patch):
    lease, inputs = _pair()
    calls = []
    for module, name in ((auth_owner, "validate_synthetic_runtime_authorization"),
            (runtime_owner, "validate_synthetic_runtime_execution_lease"),
            (request_owner, "validate_synthetic_reflection_request"),
            (admission_owner, "validate_synthetic_reflection_execution_admission")):
        original = getattr(module, name)

        def tracked(*args, original=original, name=name, **kwargs):
            calls.append(name)
            return original(*args, **kwargs)

        safe_patch.setattr(module, name, tracked)
    assert _ready(lease, inputs, owner.BEFORE_ROLE)
    assert len(set(calls)) == 4
    calls.clear()
    _activate(inputs)
    calls.clear()
    _consume(lease, inputs, owner.BEFORE_ROLE)
    assert len(set(calls)) == 4


def test_runtime_invalidation_after_precheck_cannot_start_reflection():
    lease, inputs = _pair()
    assert _ready(lease, inputs, owner.BEFORE_ROLE)
    runtime_owner.invalidate_synthetic_runtime_execution_lease(inputs[2], inputs[3])
    assert not _ready(lease, inputs, owner.BEFORE_ROLE) and not _active(lease, inputs, owner.BEFORE_ROLE)
    _reject(lambda: _consume(lease, inputs, owner.BEFORE_ROLE))
    assert lease.lifecycle_state == owner.ISSUED


def test_strict_proof_consumes_nothing_and_has_no_external_effects(safe_patch):
    def forbidden(*args, **kwargs):
        raise AssertionError("strict proof consumed a lease")

    safe_patch.setattr(runtime_owner, "consume_synthetic_runtime_execution_lease", forbidden)
    safe_patch.setattr(owner, "consume_synthetic_reflection_execution_lease", forbidden)
    from scripts.replay_synth_reflect_lifecycle1 import replay
    report = replay()
    assert report["status"] == owner.COMPLETE
    for name in ("final_strict_runtime_lease_state", "final_strict_before_lease_state", "final_strict_after_lease_state"):
        assert report[name] == owner.ISSUED
    for name, value in report.items():
        if name.endswith(("_count", "_consumptions", "_calls", "_attempts", "_created", "_consumed")) and name != "supported_lifecycle_scope_count":
            assert type(value) is int and value == 0
    assert report["effect_denial"] == {"strict": True, "denied_attempts": {}, "thread_start_attempts": 0}
    assert report["preexecution_executor_compatibility"] == {"before": True, "after": True}
    assert not report["executor_retry_performed"] and not report["source_projected"]
    assert owner.EXECUTOR_SEQUENCE[5] == "invoke exact public decrement(3)"
