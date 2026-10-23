"""SYNTH.REFLECT.LIFECYCLE.1: two single-use effects in one synthetic activation.

This additive owner authenticates all four frozen upstream capabilities through
their public owners. It never executes reflection, Java or an executor. A ready
lease requires an ISSUED runtime lease; spending it requires that exact runtime
lease to be CONSUMED. The executor owns ordering of reads and public invocation.
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
from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as runtime_owner
from core.runtime.synthetic import synthetic_read_only_reflection as request_owner
from core.runtime.synthetic import synthetic_reflection_execution_admission as admission_owner

PHASE_ID = "SYNTH.REFLECT.LIFECYCLE.1"
SCHEMA_VERSION = "synthetic_reflection_execution_lease_v1"
SCENARIO_PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
SCENARIO_ID = "synthetic.EXECUTOR.1R.decrement_3"
SOURCE_SHA256 = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
DEFINITION_SHA256 = "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d"
OWNER, MEMBER, DECLARED_TYPE = "SyntheticStateBox", "value", "int"
OPERATION = "read_exact_bound_field"
BEFORE_ROLE = "exact_private_state_before"
AFTER_ROLE = "exact_private_state_after"
SUPPORTED_ROLES = (BEFORE_ROLE, AFTER_ROLE)
ISSUED, CONSUMED, INVALIDATED = "ISSUED", "CONSUMED", "INVALIDATED"
COMPLETE = "SYNTH_REFLECT_LIFECYCLE_1_COMPLETE"
EXECUTOR_SEQUENCE = (
    "all capability/authentication gates", "source/harness ready",
    "consume scenario runtime lease", "consume BEFORE reflection lease",
    "perform BEFORE exact reflection read", "invoke exact public decrement(3)",
    "consume AFTER reflection lease", "perform AFTER exact reflection read",
)
RUNTIME_STATE_RULE = (
    "issuance and pre-execution readiness require the exact runtime lease ISSUED; "
    "reflection consumption requires the same activation's runtime lease CONSUMED"
)

_SECRET = secrets.token_bytes(32)
_ISSUER_PID = os.getpid()
_LOCK = Lock()
# Permanent process-local records, including collected and terminal leases.
_ADMISSION_LEASES: dict[str, str] = {}
_LEASES: dict[str, _LeaseRecord] = {}


class SyntheticReflectionExecutionLeaseError(ValueError):
    def __init__(self, code: str, reason: str = ""):
        self.code = code
        self.reason = reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code: str, reason: str = ""):
    raise SyntheticReflectionExecutionLeaseError(code, reason)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hex_id(value):
    return (type(value) is str and len(value) == 64
        and all(character in "0123456789abcdef" for character in value))


def _local_process():
    if type(os.getpid()) is not int or os.getpid() != _ISSUER_PID:
        _fail("synthetic_reflection_lease_unauthenticated", "issuing process required")


def _local_lock():
    _local_process()  # Reject a foreign process before an inherited lock wait.
    return _LOCK


def _role(role):
    if type(role) is not str or role not in SUPPORTED_ROLES:
        _fail("synthetic_reflection_lease_scope_mismatch", "exact BEFORE or AFTER role required")


def _authenticate_inputs(admission, request, runtime, authorization, role):
    _role(role)
    try:
        spec = authorization_owner.executor1r_decrement_3_spec()
        authorization_owner.validate_synthetic_runtime_authorization(authorization,
            spec=spec, source=authorization_owner.get_executor1r_decrement_3_source())
        runtime_owner.validate_synthetic_runtime_execution_lease(runtime, authorization)
        request_owner.validate_synthetic_reflection_request(request)
        admission_owner.validate_synthetic_reflection_execution_admission(admission)
        compatible = admission_owner.synthetic_reflection_admission_satisfies_executor(
            admission, authorization, request)
    except Exception as error:
        _fail("synthetic_reflection_lease_upstream_authentication_failed",
            getattr(error, "code", type(error).__name__))
    if compatible is not True:
        _fail("synthetic_reflection_lease_binding_mismatch", "exact admission/request/authorization pair required")
    for capability, phase_field in ((authorization, "scenario_phase_id"), (runtime, "scenario_phase_id"),
            (request, "phase_id"), (admission, "scenario_phase_id")):
        if (getattr(capability, phase_field) != SCENARIO_PHASE_ID
                or capability.scenario_id != SCENARIO_ID or capability.source_sha256 != SOURCE_SHA256):
            _fail("synthetic_reflection_lease_scope_mismatch", "exact synthetic scenario required")
    for capability in (request, admission):
        if (capability.observation_role != role or capability.definition_sha256 != DEFINITION_SHA256
                or (capability.owner, capability.member, capability.declared_type, capability.operation)
                != (OWNER, MEMBER, DECLARED_TYPE, OPERATION)):
            _fail("synthetic_reflection_lease_scope_mismatch", "exact role and field read required")
    if (runtime.upstream_authorization_issuance_id != authorization.issuance_id
            or runtime.upstream_authorization_fingerprint != authorization.fingerprint):
        _fail("synthetic_reflection_lease_binding_mismatch", "one shared activation authorization required")


class _LocalLease:
    __slots__ = ("__weakref__",)


@dataclass(frozen=True, slots=True)
class SyntheticReflectionExecutionLease(_LocalLease):
    scenario_phase_id: str
    scenario_id: str
    source_sha256: str
    definition_sha256: str
    owner: str
    member: str
    declared_type: str
    operation: str
    observation_role: str
    reflection_request_issuance_id: str
    reflection_request_fingerprint: str
    reflection_admission_id: str
    reflection_admission_fingerprint: str
    runtime_execution_lease_id: str
    runtime_execution_lease_fingerprint: str
    upstream_authorization_issuance_id: str
    upstream_authorization_fingerprint: str
    lease_id: str
    issuing_process_id: int
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    issuer_phase_id: str = field(default=PHASE_ID, init=False)
    initial_lifecycle_state: str = field(default=ISSUED, init=False)
    synthetic_reflection_execution_lease: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)
    shell_authority: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    generic_reflection_authority: bool = field(default=False, init=False)
    field_write_authority: bool = field(default=False, init=False)
    enumeration_authority: bool = field(default=False, init=False)
    private_method_authority: bool = field(default=False, init=False)
    constructor_reflection_authority: bool = field(default=False, init=False)
    arbitrary_class_loading_authority: bool = field(default=False, init=False)

    @property
    def scenario_execution_lease_id(self):
        return self.runtime_execution_lease_id

    @property
    def scenario_execution_lease_fingerprint(self):
        return self.runtime_execution_lease_fingerprint

    @property
    def lifecycle_state(self):
        return synthetic_reflection_execution_lease_state(self)

    @property
    def fingerprint(self):
        with _local_lock():
            record = _authenticated_record_locked(self)
            return sha256(record.projection_json.encode("utf8")).hexdigest()

    def as_dict(self):
        with _local_lock():
            record = _authenticated_record_locked(self)
            return {**_projection(self), "lifecycle_state": record.lifecycle_state,
                "lease_fingerprint": sha256(record.projection_json.encode("utf8")).hexdigest(),
                "report_only": True}


@dataclass(frozen=True, slots=True)
class _LeaseRecord:
    admission: admission_owner.SyntheticReflectionExecutionAdmission
    request: request_owner.SyntheticReflectionRequest
    runtime: runtime_owner.SyntheticRuntimeExecutionLease
    authorization: authorization_owner.SyntheticRuntimeAuthorization
    observation_role: str
    lease_ref: ref
    projection_json: str
    lifecycle_state: str
    signature: str


def _projection(lease):
    return {item.name: getattr(lease, item.name) for item in fields(SyntheticReflectionExecutionLease)}


def _unsigned_lease(admission, request, runtime, authorization, role, lease_id):
    return SyntheticReflectionExecutionLease(
        SCENARIO_PHASE_ID, SCENARIO_ID, SOURCE_SHA256, DEFINITION_SHA256,
        OWNER, MEMBER, DECLARED_TYPE, OPERATION, role, request.issuance_id, request.fingerprint,
        admission.admission_id, admission.fingerprint, runtime.lease_id, runtime.fingerprint,
        authorization.issuance_id, authorization.fingerprint, lease_id, _ISSUER_PID)


def _sign(projection_json, state):
    payload = _json({"immutable_issuance_projection": projection_json, "lifecycle_state": state})
    return hmac.new(_SECRET, payload.encode("utf8"), "sha256").hexdigest()


def _authenticated_record_locked(lease):
    _local_process()
    if (type(lease) is not SyntheticReflectionExecutionLease
            or not _hex_id(getattr(lease, "lease_id", None))):
        _fail("synthetic_reflection_lease_unauthenticated", "owner-issued typed live lease required")
    record = _LEASES.get(lease.lease_id)
    if type(record) is not _LeaseRecord or record.lease_ref() is not lease:
        _fail("synthetic_reflection_lease_unauthenticated", "live lease identity required")
    _authenticate_inputs(record.admission, record.request, record.runtime,
        record.authorization, record.observation_role)
    if _ADMISSION_LEASES.get(record.admission.admission_id) != lease.lease_id:
        _fail("synthetic_reflection_lease_binding_mismatch", "permanent admission binding required")
    expected = _projection(_unsigned_lease(record.admission, record.request, record.runtime,
        record.authorization, record.observation_role, lease.lease_id))
    try:
        payload = _projection(lease)
        coherent = (all(type(payload[key]) is type(value) and payload[key] == value
            for key, value in expected.items()) and _json(payload) == record.projection_json)
    except (AttributeError, TypeError, ValueError):
        coherent = False
    if not coherent:
        _fail("synthetic_reflection_lease_scope_mismatch", "exact immutable issuance required")
    if (type(record.lifecycle_state) is not str or record.lifecycle_state not in (ISSUED, CONSUMED, INVALIDATED)
            or not _hex_id(record.signature)
            or not hmac.compare_digest(record.signature, _sign(record.projection_json, record.lifecycle_state))):
        _fail("synthetic_reflection_lease_unauthenticated", "authenticated current state required")
    return record


def _bound_record_locked(lease, admission, request, runtime, authorization, role):
    _role(role)
    record = _authenticated_record_locked(lease)
    if (admission is not record.admission or request is not record.request
            or runtime is not record.runtime or authorization is not record.authorization
            or role != record.observation_role):
        _fail("synthetic_reflection_lease_binding_mismatch", "exact live inputs and observation role required")
    return record


def _runtime_state(runtime, authorization, required):
    try:
        state = runtime_owner.synthetic_runtime_execution_lease_state(runtime, authorization)
    except Exception as error:
        _fail("synthetic_reflection_lease_upstream_authentication_failed", getattr(error, "code", type(error).__name__))
    if state != required:
        _fail("synthetic_reflection_lease_runtime_not_" + required.lower(), state)


def issue_synthetic_reflection_execution_lease(admission, request, runtime, authorization, *, observation_role):
    """At most one lease per authenticated admission, including after collection."""
    with _local_lock():
        _authenticate_inputs(admission, request, runtime, authorization, observation_role)
        if admission.admission_id in _ADMISSION_LEASES:
            _fail("synthetic_reflection_admission_already_leased")
        lease_id = secrets.token_hex(32)
        while lease_id in _LEASES:
            lease_id = secrets.token_hex(32)
        lease = _unsigned_lease(admission, request, runtime, authorization, observation_role, lease_id)
        projection_json = _json(_projection(lease))
        record = _LeaseRecord(admission, request, runtime, authorization, observation_role,
            ref(lease), projection_json, ISSUED, _sign(projection_json, ISSUED))
        # The last upstream state check is the issuance eligibility point. The
        # frozen runtime owner has its own lock; we use only its public API.
        # Later runtime activation can make a precheck stale, never refundable.
        _runtime_state(runtime, authorization, ISSUED)
        _LEASES[lease_id] = record
        _ADMISSION_LEASES[admission.admission_id] = lease_id
    return lease


def validate_synthetic_reflection_execution_lease(lease):
    """Authenticate retained live upstreams and state, including terminal evidence."""
    with _local_lock():
        _authenticated_record_locked(lease)
    return lease


def synthetic_reflection_execution_lease_state(lease):
    with _local_lock():
        return _authenticated_record_locked(lease).lifecycle_state


def _compatible(lease, admission, request, runtime, authorization, role, runtime_state):
    try:
        with _local_lock():
            record = _bound_record_locked(lease, admission, request, runtime, authorization, role)
            _runtime_state(runtime, authorization, runtime_state)
            return record.lifecycle_state == ISSUED
    except SyntheticReflectionExecutionLeaseError:
        return False


def synthetic_reflection_execution_lease_satisfies_executor(
        lease, admission, request, runtime, authorization, *, observation_role):
    """Pure pre-execution precheck: both leases must still be ISSUED."""
    return _compatible(lease, admission, request, runtime, authorization, observation_role, ISSUED)


def consumable_during_active_execution(lease, admission, request, runtime, authorization, *, observation_role):
    """Pure active-execution precheck: the exact runtime lease must be CONSUMED."""
    return _compatible(lease, admission, request, runtime, authorization, observation_role, CONSUMED)


def _transition(lease, admission, request, runtime, authorization, role, target):
    with _local_lock():
        if target not in (CONSUMED, INVALIDATED):
            _fail("synthetic_reflection_lease_transition_forbidden")
        record = _bound_record_locked(lease, admission, request, runtime, authorization, role)
        if record.lifecycle_state != ISSUED:
            _fail("synthetic_reflection_lease_not_issued", record.lifecycle_state)
        if target == CONSUMED:
            # CONSUMED is terminal in the frozen runtime owner. Once this public
            # check succeeds, another runtime transition cannot revoke it.
            _runtime_state(runtime, authorization, CONSUMED)
        updated = replace(record, lifecycle_state=target, signature=_sign(record.projection_json, target))
        _LEASES[lease.lease_id] = updated  # Single transition linearization point.
    return lease


def consume_synthetic_reflection_execution_lease(
        lease, admission, request, runtime, authorization, *, observation_role):
    """Spend only this exact reflection effect; never spend runtime authority."""
    return _transition(lease, admission, request, runtime, authorization, observation_role, CONSUMED)


def invalidate_synthetic_reflection_execution_lease(
        lease, admission, request, runtime, authorization, *, observation_role):
    """Permanently abandon an ISSUED reflection lease, even if runtime was invalidated."""
    return _transition(lease, admission, request, runtime, authorization, observation_role, INVALIDATED)


def verify():
    """Strict proof: one fresh activation, two exact reads, no consumption/effects."""
    spec = authorization_owner.executor1r_decrement_3_spec()
    authorization = authorization_owner.issue_synthetic_runtime_authorization(spec,
        source=authorization_owner.get_executor1r_decrement_3_source())
    runtime = runtime_owner.issue_synthetic_runtime_execution_lease(authorization)
    handles = {"authorization": authorization, "runtime": runtime}
    duplicates, compatible = {}, {}
    for label, role, factory in (("before", BEFORE_ROLE, request_owner.executor1r_before_request),
            ("after", AFTER_ROLE, request_owner.executor1r_after_request)):
        request = factory()
        admission = admission_owner.issue_synthetic_reflection_execution_admission(authorization, request)
        lease = issue_synthetic_reflection_execution_lease(admission, request, runtime, authorization,
            observation_role=role)
        handles.update({label + "_request": request, label + "_admission": admission, label + "_lease": lease})
        validate_synthetic_reflection_execution_lease(lease)
        compatible[label] = synthetic_reflection_execution_lease_satisfies_executor(
            lease, admission, request, runtime, authorization, observation_role=role)
        try:
            issue_synthetic_reflection_execution_lease(admission, request, runtime, authorization, observation_role=role)
        except SyntheticReflectionExecutionLeaseError as error:
            duplicates[label] = error.code
        else:
            raise AssertionError("duplicate reflection lease issuance succeeded")
        assert compatible[label] and lease.lifecycle_state == ISSUED
    before, after = handles["before_lease"], handles["after_lease"]
    assert before.runtime_execution_lease_id == after.runtime_execution_lease_id == runtime.lease_id
    assert before.runtime_execution_lease_fingerprint == after.runtime_execution_lease_fingerprint == runtime.fingerprint
    assert runtime.lifecycle_state == ISSUED
    report = {
        "phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION, "status": COMPLETE, "report_only": True,
        "supported_lifecycle_scope_count": 2, "supported_roles": list(SUPPORTED_ROLES),
        "scenario_phase_id": SCENARIO_PHASE_ID, "scenario_id": SCENARIO_ID,
        "source_sha256": SOURCE_SHA256, "definition_sha256": DEFINITION_SHA256,
        "owner": OWNER, "member": MEMBER, "declared_type": DECLARED_TYPE, "operation": OPERATION,
        "synthetic_authorization": authorization.as_dict(), "runtime_execution_lease": runtime.as_dict(),
        "before_reflection_lease": before.as_dict(), "after_reflection_lease": after.as_dict(),
        "before_request": handles["before_request"].as_dict(), "after_request": handles["after_request"].as_dict(),
        "before_admission": handles["before_admission"].as_dict(), "after_admission": handles["after_admission"].as_dict(),
        "shared_runtime_execution_lease_id": runtime.lease_id,
        "shared_runtime_execution_lease_fingerprint": runtime.fingerprint,
        "common_authorization_issuance_id": authorization.issuance_id,
        "common_authorization_fingerprint": authorization.fingerprint,
        "duplicate_issuance_results": duplicates, "preexecution_executor_compatibility": compatible,
        "role_isolation_enforced": True, "exact_mutual_binding_authenticated": True,
        "final_strict_runtime_lease_state": runtime.lifecycle_state,
        "final_strict_before_lease_state": before.lifecycle_state,
        "final_strict_after_lease_state": after.lifecycle_state,
        "atomicity_mechanism": "one process-local threading.Lock around authenticate/check/sign/registry replacement",
        "runtime_state_rule": RUNTIME_STATE_RULE, "future_executor_sequence": list(EXECUTOR_SEQUENCE),
        "executor_owns_public_invocation_and_read_order": True,
        "authentication": "independent process-local HMAC-SHA256; live identity; retained upstreams; signed private current state",
        "tombstones": "permanent per-admission and terminal/dead-lease records for process lifetime",
        "invalidation_semantics": "ISSUED -> INVALIDATED; terminal; no refund or reissuance",
        "reflection_lease_consumption_implemented": True, "frozen_admissions_mutated": False,
        "exported_json_can_recreate_authority": False, "executor_retry_performed": False,
        "source_projected": False, "harness_rendered": False,
        "measured_observations": None, "positive_runtime_receipt": None,
    }
    for name in ("strict_runtime_lease_consumptions", "strict_reflection_lease_consumptions",
            "test_only_runtime_lease_consumptions", "test_only_reflection_lease_consumptions",
            "real_runtime_authorizations_consumed", "java_compile_count", "jvm_execution_count",
            "reflection_execution_count", "behavioral_execution_count", "containers_created", "docker_calls",
            "child_processes", "network_calls", "shell_calls", "thread_start_attempts", "repository_writes",
            "apply_actions", "bank_execution_count"):
        report[name] = 0
    return handles, report
