"""SYNTH.AUTH.LIFECYCLE.1: one process-local activation of frozen synthetic scope.

SYNTH.AUTH.1 remains immutable. This owner authenticates that public handle and
owns a separate, terminal state machine. Registry entries retain the upstream
handle and a weak lease identity for the process lifetime: collecting a lease
does not refund its authorization. No exported projection can restore a lease.

The immutable issuance projection and the current lifecycle state are signed
together in a private, immutable registry record. A transition replaces that
record under one lock; it never edits the public dataclass or the upstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from hashlib import sha256
import hmac
import json
import os
import secrets
from threading import Lock
from weakref import ref

from core.runtime.synthetic import synthetic_runtime_authorization as authorization_owner

PHASE_ID = "SYNTH.AUTH.LIFECYCLE.1"
SCHEMA_VERSION = "synthetic_runtime_execution_lease_v1"
SCENARIO_PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
SCENARIO_ID = "synthetic.EXECUTOR.1R.decrement_3"
SOURCE_KIND = "phase_owned_synthetic_fixture"
SOURCE_SHA256 = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
INVOCATION_OWNER = "SyntheticStateBox"
INVOCATION_METHOD = "decrement"
INVOCATION_ARGUMENT = 3
ISSUED = "ISSUED"
CONSUMED = "CONSUMED"
INVALIDATED = "INVALIDATED"
COMPLETE = "SYNTH_AUTH_LIFECYCLE_1_COMPLETE"
CONSUMPTION_POLICY = (
    "after synthetic authorization, both reflection requests/admissions, SANDBOX.2, "
    "JAVA.1 and exact source/harness readiness authenticate; immediately before "
    "the first behavioral runtime effect; no refund after any subsequent failure"
)
COMPILATION_POLICY = (
    "preserve the existing infrastructure/structural compilation contract; "
    "this owner grants no compilation authority; a future executor must report "
    "any contract that classifies compilation as runtime activation before proceeding"
)

_SECRET = secrets.token_bytes(32)
_ISSUER_PID = os.getpid()
_LOCK = Lock()
# Permanent process-local tombstones, including dead, consumed and invalidated
# leases. Keys originate only from authenticated upstream handles and our RNG.
_AUTHORIZATION_LEASES: dict[str, str] = {}
_LEASES: dict[str, _LeaseRecord] = {}


class SyntheticRuntimeExecutionLeaseError(ValueError):
    def __init__(self, code: str, reason: str = ""):
        self.code = code
        self.reason = reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code: str, reason: str = ""):
    raise SyntheticRuntimeExecutionLeaseError(code, reason)


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hex_id(value) -> bool:
    return (type(value) is str and len(value) == 64
        and all(character in "0123456789abcdef" for character in value))


def _local_process():
    if type(os.getpid()) is not int or os.getpid() != _ISSUER_PID:
        _fail("synthetic_runtime_lease_unauthenticated", "issuing process required")


def _local_lock():
    # Reject a forked process before waiting on a potentially inherited lock.
    _local_process()
    return _LOCK


def _authenticate_authorization(authorization):
    try:
        spec = authorization_owner.executor1r_decrement_3_spec()
        source = authorization_owner.get_executor1r_decrement_3_source()
        authorization_owner.validate_synthetic_runtime_authorization(
            authorization, spec=spec, source=source)
    except authorization_owner.SyntheticRuntimeAuthorizationError as error:
        _fail("synthetic_runtime_lease_upstream_authentication_failed", error.code)
    invocation = spec.invocation_contract
    if (spec.phase_id != SCENARIO_PHASE_ID or spec.scenario_id != SCENARIO_ID
            or spec.source_kind != SOURCE_KIND or spec.source_sha256 != SOURCE_SHA256
            or invocation.owner != INVOCATION_OWNER
            or invocation.public_method != INVOCATION_METHOD
            or invocation.arguments != (INVOCATION_ARGUMENT,)
            or invocation.argument_types != ("int",) or invocation.return_type != "boolean"):
        _fail("synthetic_runtime_lease_scope_mismatch", "only the exact decrement(3) scope is supported")
    return authorization


class _LocalLease:
    __slots__ = ("__weakref__",)


@dataclass(frozen=True, slots=True)
class SyntheticRuntimeExecutionLease(_LocalLease):
    """Immutable local identity; current state is authenticated by its owner."""

    upstream_authorization_issuance_id: str
    upstream_authorization_fingerprint: str
    scenario_phase_id: str
    scenario_id: str
    source_kind: str
    source_sha256: str
    invocation_owner: str
    invocation_method: str
    invocation_argument: int
    lease_id: str
    issuing_process_id: int
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    issuer_phase_id: str = field(default=PHASE_ID, init=False)
    initial_lifecycle_state: str = field(default=ISSUED, init=False)
    synthetic_runtime_execution_lease: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)
    shell_authority: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    reflection_authority: bool = field(default=False, init=False)

    @property
    def lifecycle_state(self) -> str:
        return synthetic_runtime_execution_lease_state(self)

    @property
    def fingerprint(self) -> str:
        with _local_lock():
            record = _authenticated_record_locked(self)
            return sha256(record.projection_json.encode("utf8")).hexdigest()

    def as_dict(self) -> dict:
        with _local_lock():
            record = _authenticated_record_locked(self)
            return {**_projection(self), "lifecycle_state": record.lifecycle_state,
                "lease_fingerprint": sha256(record.projection_json.encode("utf8")).hexdigest(),
                "report_only": True}


@dataclass(frozen=True, slots=True)
class _LeaseRecord:
    authorization: authorization_owner.SyntheticRuntimeAuthorization
    lease_ref: ref
    projection_json: str
    lifecycle_state: str
    signature: str


def _projection(lease) -> dict:
    return {item.name: getattr(lease, item.name)
        for item in fields(SyntheticRuntimeExecutionLease)}


def _unsigned_lease(authorization, lease_id):
    return SyntheticRuntimeExecutionLease(authorization.issuance_id, authorization.fingerprint,
        SCENARIO_PHASE_ID, SCENARIO_ID, SOURCE_KIND, SOURCE_SHA256,
        INVOCATION_OWNER, INVOCATION_METHOD, INVOCATION_ARGUMENT, lease_id, _ISSUER_PID)


def _sign(projection_json, state) -> str:
    payload = _json({"immutable_issuance_projection": projection_json, "lifecycle_state": state})
    return hmac.new(_SECRET, payload.encode("utf8"), "sha256").hexdigest()


def _authenticated_record_locked(lease, authorization=None):
    """Caller holds _LOCK through authentication and any subsequent transition."""
    _local_process()
    if type(lease) is not SyntheticRuntimeExecutionLease or not _hex_id(lease.lease_id):
        _fail("synthetic_runtime_lease_unauthenticated", "owner-issued typed live lease required")
    record = _LEASES.get(lease.lease_id)
    if type(record) is not _LeaseRecord or record.lease_ref() is not lease:
        _fail("synthetic_runtime_lease_unauthenticated", "live lease identity required")
    upstream = record.authorization
    if authorization is not None and authorization is not upstream:
        _fail("synthetic_runtime_lease_binding_mismatch", "exact live upstream authorization required")
    _authenticate_authorization(upstream)
    if _AUTHORIZATION_LEASES.get(upstream.issuance_id) != lease.lease_id:
        _fail("synthetic_runtime_lease_binding_mismatch", "authoritative issuance binding required")
    expected = _projection(_unsigned_lease(upstream, lease.lease_id))
    payload = _projection(lease)
    if (any(type(payload[key]) is not type(value) or payload[key] != value
            for key, value in expected.items()) or _json(payload) != record.projection_json):
        _fail("synthetic_runtime_lease_scope_mismatch", "exact immutable issuance projection required")
    if (type(record.lifecycle_state) is not str
            or record.lifecycle_state not in (ISSUED, CONSUMED, INVALIDATED)
            or not _hex_id(record.signature)
            or not hmac.compare_digest(record.signature,
                _sign(record.projection_json, record.lifecycle_state))):
        _fail("synthetic_runtime_lease_unauthenticated", "owner-authenticated lifecycle state required")
    return record


def issue_synthetic_runtime_execution_lease(authorization):
    """Reject duplicate issuance even when the prior lease is terminal or dead."""
    with _local_lock():
        _local_process()
        _authenticate_authorization(authorization)
        if authorization.issuance_id in _AUTHORIZATION_LEASES:
            _fail("synthetic_runtime_authorization_already_leased")
        lease_id = secrets.token_hex(32)
        while lease_id in _LEASES:
            lease_id = secrets.token_hex(32)
        lease = _unsigned_lease(authorization, lease_id)
        projection_json = _json(_projection(lease))
        record = _LeaseRecord(authorization, ref(lease), projection_json, ISSUED,
            _sign(projection_json, ISSUED))
        _LEASES[lease_id] = record
        _AUTHORIZATION_LEASES[authorization.issuance_id] = lease_id
        return lease


def validate_synthetic_runtime_execution_lease(lease, authorization=None):
    """Authenticate identity and current state, including terminal evidence.

    Omitting authorization authenticates the retained upstream handle. Supplying
    it also requires that exact live object. Validity does not imply readiness.
    """
    with _local_lock():
        _authenticated_record_locked(lease, authorization)
    return lease


def synthetic_runtime_execution_lease_state(lease, authorization=None) -> str:
    with _local_lock():
        return _authenticated_record_locked(lease, authorization).lifecycle_state


def lease_is_issued(lease, authorization=None) -> bool:
    return synthetic_runtime_execution_lease_state(lease, authorization) == ISSUED


def lease_is_consumed(lease, authorization=None) -> bool:
    return synthetic_runtime_execution_lease_state(lease, authorization) == CONSUMED


def synthetic_runtime_execution_lease_satisfies_executor(lease, authorization) -> bool:
    """Pure precheck; consumption must reauthenticate under the same owner lock."""
    try:
        # None is not an executor authorization, even though inspection can
        # deliberately omit it and authenticate the retained upstream instead.
        if authorization is None:
            return False
        with _local_lock():
            return _authenticated_record_locked(lease, authorization).lifecycle_state == ISSUED
    except SyntheticRuntimeExecutionLeaseError:
        return False


def _transition(lease, authorization, target):
    with _local_lock():
        if target not in (CONSUMED, INVALIDATED):
            _fail("synthetic_runtime_lease_transition_forbidden")
        if authorization is None:
            _fail("synthetic_runtime_lease_binding_mismatch", "live upstream authorization required")
        record = _authenticated_record_locked(lease, authorization)
        if record.lifecycle_state != ISSUED:
            _fail("synthetic_runtime_lease_not_issued", record.lifecycle_state)
        updated = replace(record, lifecycle_state=target,
            signature=_sign(record.projection_json, target))
        # This assignment is the linearization point. All readers, issuers and
        # competing transitions use the same lock. Nothing refundable follows.
        _LEASES[lease.lease_id] = updated
    return lease


def consume_synthetic_runtime_execution_lease(lease, authorization):
    """Activate exactly once. Any later failure leaves the lease CONSUMED."""
    return _transition(lease, authorization, CONSUMED)


def invalidate_synthetic_runtime_execution_lease(lease, authorization):
    """Optionally abandon an ISSUED lease permanently, without consuming it."""
    return _transition(lease, authorization, INVALIDATED)


def verify():
    """Issue one strict-proof pair and leave its lease ISSUED and unconsumed."""
    spec = authorization_owner.executor1r_decrement_3_spec()
    authorization = authorization_owner.issue_synthetic_runtime_authorization(spec,
        source=authorization_owner.get_executor1r_decrement_3_source())
    lease = issue_synthetic_runtime_execution_lease(authorization)
    validate_synthetic_runtime_execution_lease(lease, authorization)
    compatible = synthetic_runtime_execution_lease_satisfies_executor(lease, authorization)
    try:
        issue_synthetic_runtime_execution_lease(authorization)
    except SyntheticRuntimeExecutionLeaseError as error:
        duplicate_result = error.code
    else:
        raise AssertionError("duplicate lifecycle issuance succeeded")
    assert compatible and lease_is_issued(lease, authorization)
    report = {
        "phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION, "status": COMPLETE,
        "report_only": True, "supported_lifecycle_scope_count": 1,
        "synthetic_authorization": authorization.as_dict(), "execution_lease": lease.as_dict(),
        "synthetic_runtime_authorizations_issued": 1, "execution_leases_issued": 1,
        "duplicate_lease_issuance_result": duplicate_result,
        "upstream_authenticated_in_issuing_process": True,
        "lease_authenticated_in_issuing_process": True,
        "executor_compatibility": compatible,
        "initial_lifecycle_state": ISSUED, "final_strict_proof_lease_state": lease.lifecycle_state,
        "atomicity_mechanism": "one process-local threading.Lock; authenticate/check/replace under lock",
        "live_identity_registry": "weak lease identity; retained upstream identity; permanent process-local tombstones",
        "authentication": "independent process-local HMAC-SHA256 over immutable issuance projection and current state",
        "exported_json_can_recreate_authority": False,
        "invalidation_semantics": "ISSUED -> INVALIDATED; terminal; no consumption or reissuance",
        "consumption_policy": CONSUMPTION_POLICY, "compilation_policy": COMPILATION_POLICY,
        "reflection_admission_consumption_implemented": False,
        "executor_retry_performed": False, "source_projected": False, "harness_rendered": False,
        "measured_observations": None, "positive_runtime_receipt": None,
        "test_only_lease_consumptions": 0,
    }
    for name in ("synthetic_runtime_authorizations_consumed", "real_runtime_authorizations_consumed",
            "java_compile_count", "compile_count", "jvm_execution_count", "reflection_execution_count",
            "behavioral_execution_count", "synthetic_behavioral_execution_count", "bank_execution_count",
            "containers_created", "docker_calls", "network_calls", "shell_calls", "child_processes",
            "thread_start_attempts", "repository_writes", "apply_actions"):
        report[name] = 0
    return (authorization, lease), report
