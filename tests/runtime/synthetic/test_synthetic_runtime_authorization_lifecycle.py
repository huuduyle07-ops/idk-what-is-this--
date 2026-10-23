"""Pure lifecycle contracts: no Java, processes, networks, writes or threads."""
from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, fields, replace
import gc
from itertools import permutations
import json
from types import SimpleNamespace
from unittest.mock import patch
from weakref import ref

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core.runtime.synthetic import synthetic_runtime_authorization as upstream
    from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as owner


# Verification bookkeeping only, never consulted by the production owner.
TEST_ONLY_CONSUMPTIONS = []


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


def _auth():
    return upstream.issue_synthetic_runtime_authorization(upstream.executor1r_decrement_3_spec(),
        source=upstream.get_executor1r_decrement_3_source())


def _pair():
    auth = _auth()
    return auth, owner.issue_synthetic_runtime_execution_lease(auth)


def _consume(lease, auth):
    result = owner.consume_synthetic_runtime_execution_lease(lease, auth)
    TEST_ONLY_CONSUMPTIONS.append(lease.lease_id)
    return result


def _reject(operation, code=None):
    with pytest.raises(owner.SyntheticRuntimeExecutionLeaseError) as caught:
        operation()
    if code:
        assert caught.value.code == code
    assert type(caught.value.code) is str and caught.value.code


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


def test_exact_scope_and_authority_separation():
    auth, lease = _pair()
    assert owner.validate_synthetic_runtime_execution_lease(lease, auth) is lease
    assert owner.validate_synthetic_runtime_execution_lease(lease) is lease
    assert lease.schema_version == "synthetic_runtime_execution_lease_v1"
    assert lease.issuer_phase_id == "SYNTH.AUTH.LIFECYCLE.1"
    assert lease.upstream_authorization_issuance_id == auth.issuance_id
    assert lease.upstream_authorization_fingerprint == auth.fingerprint
    assert lease.scenario_phase_id == "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
    assert lease.scenario_id == "synthetic.EXECUTOR.1R.decrement_3"
    assert lease.source_sha256 == "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
    assert lease.source_kind == "phase_owned_synthetic_fixture"
    assert (lease.invocation_owner, lease.invocation_method, lease.invocation_argument) == (
        "SyntheticStateBox", "decrement", 3)
    assert lease.synthetic_runtime_execution_lease is True
    for name in ("runtime_authority", "real_task_runtime_authority", "repository_write_authority",
            "apply_authority", "network_authority", "host_mount_authority", "shell_authority",
            "arbitrary_command_authority", "reflection_authority"):
        assert getattr(lease, name) is False
    assert lease.initial_lifecycle_state == lease.lifecycle_state == owner.ISSUED
    assert lease.issuing_process_id == auth.issuer_process_id
    assert len(lease.lease_id) == len(lease.fingerprint) == 64


def test_duplicate_issue_is_rejected_while_issued_and_never_returns_another_ticket():
    auth, lease = _pair()
    _reject(lambda: owner.issue_synthetic_runtime_execution_lease(auth),
        "synthetic_runtime_authorization_already_leased")
    assert owner.lease_is_issued(lease, auth)


def test_one_activation_is_terminal_but_remains_authentic_historical_evidence():
    auth, lease = _pair()
    auth_before, lease_before, fingerprint = auth.as_dict(), lease.as_dict(), lease.fingerprint
    assert owner.synthetic_runtime_execution_lease_satisfies_executor(lease, auth)
    assert _consume(lease, auth) is lease
    assert owner.validate_synthetic_runtime_execution_lease(lease, auth) is lease
    assert owner.lease_is_consumed(lease, auth)
    assert not owner.lease_is_issued(lease, auth)
    assert not owner.synthetic_runtime_execution_lease_satisfies_executor(lease, auth)
    assert lease.lifecycle_state == owner.CONSUMED
    assert lease.fingerprint == fingerprint
    assert auth.as_dict() == auth_before
    assert auth.synthetic_runtime_authorizations_consumed == 0
    assert {**lease_before, "lifecycle_state": owner.CONSUMED} == lease.as_dict()
    _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth),
        "synthetic_runtime_lease_not_issued")
    _reject(lambda: owner.invalidate_synthetic_runtime_execution_lease(lease, auth))
    _reject(lambda: owner.issue_synthetic_runtime_execution_lease(auth))
    assert owner.lease_is_consumed(lease, auth)


def test_invalidation_is_terminal_without_consumption_or_reissue():
    auth, lease = _pair()
    assert owner.invalidate_synthetic_runtime_execution_lease(lease, auth) is lease
    assert owner.validate_synthetic_runtime_execution_lease(lease, auth) is lease
    assert lease.lifecycle_state == owner.INVALIDATED
    assert not owner.lease_is_issued(lease, auth)
    assert not owner.lease_is_consumed(lease, auth)
    assert not owner.synthetic_runtime_execution_lease_satisfies_executor(lease, auth)
    _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
    _reject(lambda: owner.invalidate_synthetic_runtime_execution_lease(lease, auth))
    _reject(lambda: owner.issue_synthetic_runtime_execution_lease(auth))


@pytest.mark.parametrize("state", (owner.ISSUED, owner.CONSUMED, owner.INVALIDATED))
def test_dead_lease_does_not_release_upstream_authority(state):
    auth, lease = _pair()
    if state == owner.CONSUMED:
        _consume(lease, auth)
    elif state == owner.INVALIDATED:
        owner.invalidate_synthetic_runtime_execution_lease(lease, auth)
    weak = ref(lease)
    del lease
    gc.collect()
    assert weak() is None
    _reject(lambda: owner.issue_synthetic_runtime_execution_lease(auth),
        "synthetic_runtime_authorization_already_leased")


def test_fresh_authorizations_have_independent_leases_and_wrong_pairs_fail():
    auth, lease = _pair()
    foreign, other = _pair()
    assert lease.lease_id != other.lease_id
    assert lease.fingerprint != other.fingerprint
    for operation in (owner.validate_synthetic_runtime_execution_lease,
            owner.consume_synthetic_runtime_execution_lease,
            owner.invalidate_synthetic_runtime_execution_lease,
            owner.synthetic_runtime_execution_lease_state):
        _reject(lambda: operation(lease, foreign), "synthetic_runtime_lease_binding_mismatch")
    assert not owner.synthetic_runtime_execution_lease_satisfies_executor(lease, foreign)
    assert owner.lease_is_issued(lease, auth) and owner.lease_is_issued(other, foreign)


@pytest.mark.parametrize("clone", (copy.copy, copy.deepcopy, replace,
    lambda auth: auth.as_dict(), lambda auth: json.loads(json.dumps(auth.as_dict())),
    lambda auth: auth.fingerprint, lambda auth: auth.issuance_id,
    lambda auth: SimpleNamespace(**auth.as_dict()),
    lambda auth: type(auth)(**{f.name: getattr(auth, f.name) for f in fields(auth) if f.init})))
def test_nonlive_authorization_cannot_issue_or_activate(clone):
    auth, lease = _pair()
    value = clone(auth)
    _reject(lambda: owner.issue_synthetic_runtime_execution_lease(value))
    _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, value))
    assert not owner.synthetic_runtime_execution_lease_satisfies_executor(lease, value)
    assert owner.lease_is_issued(lease, auth)


class _LeaseSubclass(owner.SyntheticRuntimeExecutionLease):
    pass


class _Wrapper:
    def __init__(self, lease):
        self.lease = lease

    def __getattr__(self, name):
        return getattr(self.lease, name)


def _reconstruct(lease, cls=owner.SyntheticRuntimeExecutionLease):
    return cls(**{f.name: getattr(lease, f.name) for f in fields(lease) if f.init})


def _json_reconstruct(lease):
    payload = json.loads(json.dumps(lease.as_dict()))
    return owner.SyntheticRuntimeExecutionLease(**{f.name: payload[f.name]
        for f in fields(lease) if f.init})


@pytest.mark.parametrize("state", (owner.ISSUED, owner.CONSUMED, owner.INVALIDATED))
@pytest.mark.parametrize("clone", (copy.copy, copy.deepcopy, replace, _reconstruct,
    lambda lease: lease.as_dict(), lambda lease: json.loads(json.dumps(lease.as_dict())),
    _json_reconstruct, lambda lease: _reconstruct(lease, _LeaseSubclass), _Wrapper,
    lambda lease: lease.fingerprint, lambda lease: lease.lease_id))
def test_copy_exports_and_reconstruction_never_restore_a_live_lease(state, clone):
    auth, lease = _pair()
    if state == owner.CONSUMED:
        _consume(lease, auth)
    elif state == owner.INVALIDATED:
        owner.invalidate_synthetic_runtime_execution_lease(lease, auth)
    value = clone(lease)
    _reject(lambda: owner.validate_synthetic_runtime_execution_lease(value, auth))
    _reject(lambda: owner.consume_synthetic_runtime_execution_lease(value, auth))
    assert not owner.synthetic_runtime_execution_lease_satisfies_executor(value, auth)
    assert lease.lifecycle_state == state


@pytest.mark.parametrize("name", tuple(f.name for f in fields(owner.SyntheticRuntimeExecutionLease)))
def test_every_issuance_field_is_authenticated_even_on_live_identity(name):
    auth, lease = _pair()
    with _set(lease, name, _different(getattr(lease, name))):
        _reject(lambda: owner.validate_synthetic_runtime_execution_lease(lease, auth))
        _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
        assert not owner.synthetic_runtime_execution_lease_satisfies_executor(lease, auth)
    assert owner.lease_is_issued(lease, auth)


@pytest.mark.parametrize("name,value", (("invocation_argument", 3.0),
    ("runtime_authority", 0), ("synthetic_runtime_execution_lease", 1),
    ("issuing_process_id", True), ("invocation_argument", True)))
def test_equal_or_foreign_primitive_types_cannot_pass_scope_binding(name, value):
    auth, lease = _pair()
    with _set(lease, name, value):
        _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
    assert owner.lease_is_issued(lease, auth)


def test_live_upstream_is_reauthenticated_using_public_validator(safe_patch):
    auth, lease = _pair()
    calls = []
    original = upstream.validate_synthetic_runtime_authorization

    def validate(value, **kwargs):
        calls.append(value)
        return original(value, **kwargs)

    safe_patch.setattr(upstream, "validate_synthetic_runtime_authorization", validate)
    assert owner.validate_synthetic_runtime_execution_lease(lease, auth) is lease
    assert calls and all(value is auth for value in calls)
    with _set(auth, "source_sha256", "f" * 64):
        _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
    assert owner.lease_is_issued(lease, auth)


@pytest.mark.parametrize("module", (upstream, owner))
def test_key_change_fails_closed_for_readiness_validation_and_consumption(safe_patch, module):
    auth, lease = _pair()
    safe_patch.setattr(module, "_SECRET", b"different-key".ljust(32, b"!"))
    _reject(lambda: owner.validate_synthetic_runtime_execution_lease(lease, auth))
    _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
    assert not owner.synthetic_runtime_execution_lease_satisfies_executor(lease, auth)
    if module is upstream:
        _reject(lambda: owner.issue_synthetic_runtime_execution_lease(auth))
    else:
        _reject(lambda: owner.issue_synthetic_runtime_execution_lease(auth),
            "synthetic_runtime_authorization_already_leased")


def test_foreign_process_rejects_all_lease_operations_without_a_process_launch(safe_patch):
    auth, lease = _pair()
    safe_patch.setattr(owner.os, "getpid", lambda: lease.issuing_process_id + 1)
    for operation in (lambda: owner.issue_synthetic_runtime_execution_lease(auth),
            lambda: owner.validate_synthetic_runtime_execution_lease(lease, auth),
            lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth),
            lambda: owner.invalidate_synthetic_runtime_execution_lease(lease, auth)):
        _reject(operation)
    assert not owner.synthetic_runtime_execution_lease_satisfies_executor(lease, auth)


def test_foreign_process_is_rejected_before_waiting_on_an_inherited_lock(safe_patch):
    auth, lease = _pair()

    class InheritedLocked:
        def __enter__(self):
            raise AssertionError("foreign process must never wait on the inherited lock")

        def __exit__(self, *args):
            pass

    safe_patch.setattr(owner.os, "getpid", lambda: lease.issuing_process_id + 1)
    safe_patch.setattr(owner, "_LOCK", InheritedLocked())
    _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
    _reject(lambda: owner.issue_synthetic_runtime_execution_lease(auth))
    _reject(lambda: owner.validate_synthetic_runtime_execution_lease(lease, auth))


@pytest.mark.parametrize("state", (owner.CONSUMED, owner.INVALIDATED, "UNKNOWN", owner.ISSUED))
def test_forged_registry_state_cannot_authenticate_or_reset_consumed_state(safe_patch, state):
    auth, lease = _pair()
    # CONSUMED -> ISSUED is specifically attempted with the old consumed MAC.
    if state == owner.ISSUED:
        _consume(lease, auth)
    record = owner._LEASES[lease.lease_id]
    with safe_patch.context() as edit:
        edit.setitem(owner._LEASES, lease.lease_id, replace(record, lifecycle_state=state))
        _reject(lambda: owner.validate_synthetic_runtime_execution_lease(lease, auth))
        _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
    assert lease.lifecycle_state == record.lifecycle_state


def test_public_object_cannot_forge_consumed_or_reset_issued_state():
    auth, lease = _pair()
    for state in (owner.CONSUMED, owner.INVALIDATED):
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            object.__setattr__(lease, "lifecycle_state", state)
    _consume(lease, auth)
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        object.__setattr__(lease, "lifecycle_state", owner.ISSUED)
    assert owner.lease_is_consumed(lease, auth)
    for name in ("reset_synthetic_runtime_execution_lease", "replay_synthetic_runtime_execution_lease",
            "restore_synthetic_runtime_execution_lease"):
        assert not hasattr(owner, name)


@pytest.mark.parametrize("failure", ("java_launch", "reflection", "method_invocation",
    "output_protocol", "timeout", "cleanup"))
def test_later_failure_cannot_refund_authority(failure):
    auth, lease = _pair()
    _consume(lease, auth)
    try:
        raise RuntimeError("test-only subsequent failure: " + failure)
    except RuntimeError:
        pass
    assert owner.lease_is_consumed(lease, auth)
    _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
    _reject(lambda: owner.issue_synthetic_runtime_execution_lease(auth))


def test_failed_checks_before_consumption_preserve_issued_state():
    auth, lease = _pair()
    foreign = _auth()
    _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, foreign))
    assert owner.lease_is_issued(lease, auth)
    assert _consume(lease, auth) is lease


_INTERLEAVINGS = tuple(order for order in permutations(("check_a", "check_b", "consume_a", "consume_b"))
    if order.index("check_a") < order.index("consume_a")
    and order.index("check_b") < order.index("consume_b"))


@pytest.mark.parametrize("order", _INTERLEAVINGS)
def test_two_callers_with_stale_prechecks_have_only_one_successful_transition(order):
    """Enumerate six valid caller schedules; no thread or scheduler is needed."""
    auth, lease = _pair()
    successes, rejections = 0, 0
    for operation in order:
        if operation.startswith("check"):
            assert owner.synthetic_runtime_execution_lease_satisfies_executor(lease, auth) == (successes == 0)
        else:
            try:
                _consume(lease, auth)
                successes += 1
            except owner.SyntheticRuntimeExecutionLeaseError as error:
                assert error.code == "synthetic_runtime_lease_not_issued"
                rejections += 1
    assert successes == rejections == 1
    assert owner.lease_is_consumed(lease, auth)


def test_issue_authentication_and_transition_commit_share_the_same_real_lock(safe_patch):
    checks, commits = [], []
    original = owner._authenticate_authorization

    def authenticate(auth):
        assert owner._LOCK.locked()
        checks.append(auth)
        return original(auth)

    class RecordingRegistry(dict):
        def __setitem__(self, key, value):
            assert owner._LOCK.locked()
            commits.append(value.lifecycle_state)
            return super().__setitem__(key, value)

    safe_patch.setattr(owner, "_authenticate_authorization", authenticate)
    safe_patch.setattr(owner, "_LEASES", RecordingRegistry(owner._LEASES))
    auth, lease = _pair()
    assert owner.synthetic_runtime_execution_lease_satisfies_executor(lease, auth)
    _consume(lease, auth)
    _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
    assert checks and commits == [owner.ISSUED, owner.CONSUMED]
    assert not owner._LOCK.locked()


@pytest.mark.parametrize("first", ("consume", "invalidate"))
def test_consumption_and_invalidation_compete_for_the_same_single_transition(first):
    auth, lease = _pair()
    if first == "consume":
        _consume(lease, auth)
        _reject(lambda: owner.invalidate_synthetic_runtime_execution_lease(lease, auth))
        assert owner.lease_is_consumed(lease, auth)
    else:
        owner.invalidate_synthetic_runtime_execution_lease(lease, auth)
        _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, auth))
        assert lease.lifecycle_state == owner.INVALIDATED


def test_closed_transition_targets_cannot_act_as_a_reset_api():
    auth, lease = _pair()
    for state in (owner.ISSUED, "UNKNOWN"):
        _reject(lambda: owner._transition(lease, auth, state),
            "synthetic_runtime_lease_transition_forbidden")
    assert owner.lease_is_issued(lease, auth)
    _consume(lease, auth)
    _reject(lambda: owner._transition(lease, auth, owner.ISSUED))
    assert owner.lease_is_consumed(lease, auth)


@pytest.mark.parametrize("state", (owner.ISSUED, owner.CONSUMED, owner.INVALIDATED))
def test_export_omits_all_signature_and_secret_material(state):
    auth, lease = _pair()
    if state == owner.CONSUMED:
        _consume(lease, auth)
    elif state == owner.INVALIDATED:
        owner.invalidate_synthetic_runtime_execution_lease(lease, auth)
    payload = lease.as_dict()
    assert payload["report_only"] is True
    assert payload["lifecycle_state"] == state
    assert not any("signature" in key or "secret" in key for key in payload)
    assert owner._LEASES[lease.lease_id].signature not in json.dumps(payload)


def test_none_or_bank_authorization_cannot_issue_or_consume():
    auth, lease = _pair()
    for value in (None, {"source_kind": "BANK", "runtime_authority": True},
            SimpleNamespace(source_kind="BANK", runtime_authority=True)):
        _reject(lambda: owner.issue_synthetic_runtime_execution_lease(value))
        _reject(lambda: owner.consume_synthetic_runtime_execution_lease(lease, value))
        assert not owner.synthetic_runtime_execution_lease_satisfies_executor(lease, value)
    assert owner.lease_is_issued(lease, auth)


def test_future_consumption_boundary_is_explicit_and_has_no_runtime_implementation():
    assert "both reflection requests/admissions" in owner.CONSUMPTION_POLICY
    assert "SANDBOX.2" in owner.CONSUMPTION_POLICY and "JAVA.1" in owner.CONSUMPTION_POLICY
    assert "immediately before the first behavioral runtime effect" in owner.CONSUMPTION_POLICY
    assert "no refund" in owner.CONSUMPTION_POLICY
    assert "classifies compilation as runtime activation" in owner.COMPILATION_POLICY


def test_strict_proof_issues_one_pair_and_never_consumes_its_final_lease(safe_patch):
    issued, consumed = [], []
    original = upstream.issue_synthetic_runtime_authorization

    def issue(*args, **kwargs):
        auth = original(*args, **kwargs)
        issued.append(auth)
        return auth

    def consume(*args, **kwargs):
        consumed.append(args)
        raise AssertionError("strict proof must not consume its lease")

    safe_patch.setattr(upstream, "issue_synthetic_runtime_authorization", issue)
    safe_patch.setattr(owner, "consume_synthetic_runtime_execution_lease", consume)
    (auth, lease), report = owner.verify()
    assert issued == [auth] and consumed == []
    assert owner.lease_is_issued(lease, auth)
    assert report["status"] == "SYNTH_AUTH_LIFECYCLE_1_COMPLETE"
    assert report["executor_compatibility"] is True
    assert report["final_strict_proof_lease_state"] == owner.ISSUED
    assert report["supported_lifecycle_scope_count"] == 1
    assert report["synthetic_runtime_authorizations_consumed"] == 0
    assert report["test_only_lease_consumptions"] == 0
    assert report["executor_retry_performed"] is False
    assert report["reflection_admission_consumption_implemented"] is False
    assert report["source_projected"] is False
    assert report["measured_observations"] is None
    for name in ("java_compile_count", "jvm_execution_count", "reflection_execution_count",
            "behavioral_execution_count", "containers_created", "docker_calls", "network_calls",
            "shell_calls", "child_processes", "bank_execution_count", "real_runtime_authorizations_consumed"):
        assert type(report[name]) is int and report[name] == 0


def test_replay_proof_remains_issued_and_strictly_effect_free():
    from scripts.replay_synth_auth_lifecycle1 import replay
    report = replay()
    assert report["status"] == owner.COMPLETE
    assert report["final_strict_proof_lease_state"] == owner.ISSUED
    assert report["effect_denial"] == {"strict": True, "denied_attempts": {}, "thread_start_attempts": 0}
    assert report["test_only_lease_consumptions"] == 0
