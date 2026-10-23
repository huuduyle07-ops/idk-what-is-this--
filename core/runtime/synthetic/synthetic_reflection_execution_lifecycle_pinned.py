"""SYNTH.REFLECT.LIFECYCLE.PINNED.1: exact one-shot reflection permission.

This independent process-local owner authenticates only unchanged public
upstream APIs and retains their exact originals. One immutable store replacement
publishes issuance or a terminal permission transition. No read, invocation,
source preparation, compilation, executor or runtime transition occurs here.
Consumer/source/compile proof remains unresolved; every behavioral readiness
report stays false. Spending permission is never evidence of a reflection read.
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

from core.runtime.synthetic import synthetic_read_only_reflection as reflection_owner
from core.runtime.synthetic import synthetic_reflection_execution_admission_pinned as admission_owner
from core.runtime.synthetic import synthetic_runtime_authorization_pinned as authorization_owner
from core.runtime.synthetic import synthetic_runtime_authorization_pinned_lifecycle as runtime_owner

OWNER_ID = "core.synthetic_reflection_execution_lifecycle_pinned"
PHASE_ID = "SYNTH.REFLECT.LIFECYCLE.PINNED.1"
SCHEMA_VERSION = "synthetic_reflection_execution_lease_pinned_1_v1"
COMPLETE = "SYNTH_REFLECT_LIFECYCLE_PINNED_1A_COMPLETE"
ISSUED, CONSUMED, INVALIDATED = "ISSUED", "CONSUMED", "INVALIDATED"
BEFORE, AFTER = "BEFORE", "AFTER"
BEFORE_ROLE, AFTER_ROLE = "exact_private_state_before", "exact_private_state_after"
SCENARIO_PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
SCENARIO_ID = "synthetic.EXECUTOR.1R.decrement_3"
SOURCE_KIND = "phase_owned_synthetic_fixture"
SOURCE_SHA256 = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
SOURCE_SIZE_BYTES = 239
DEFINITION_SHA256 = "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d"
RENDERER_IDENTITY = "SYNTH.REFLECT.1.render_synthetic_read_only_reflection"
RENDERER_PHASE = "SYNTH.REFLECT.1"
RENDERER_SCHEMA = "synthetic_reflection_request_v1"
BEFORE_HELPER_SHA256 = "c88aeea914c88ef17a335a184abe6d5b618a9c0c70a7121621ba67edd9919531"
AFTER_HELPER_SHA256 = "4d85951e886bfedabae50c7f64e8e0fa4985e8fa515e4edab9af0a355b10f4ea"
# Normative downstream ordering only. This permission owner performs no step.
EXECUTOR_SEQUENCE = (
    "all capability/authentication gates", "source/harness ready",
    "consume pinned runtime lease", "consume BEFORE reflection lease",
    "perform BEFORE exact reflection read", "invoke exact public decrement(3)",
    "consume AFTER reflection lease", "perform AFTER exact reflection read",
)
RUNTIME_STATE_RULE = (
    "issuance and preexecution readiness require the exact runtime lease ISSUED; "
    "active readiness and reflection consumption require the exact runtime lease CONSUMED; "
    "invalidation and terminal evidence require any authentic runtime state"
)
ERROR_CODES = (
    "PINNED_AUTH_UNAUTHENTICATED", "PINNED_AUTH_SCOPE_MISMATCH",
    "PINNED_PROVIDER_PROVENANCE_MISMATCH", "PINNED_RUNTIME_LEASE_UNAUTHENTICATED",
    "PINNED_RUNTIME_STATE_MISMATCH", "REFLECTION_REQUEST_UNAUTHENTICATED",
    "REFLECTION_SCOPE_MISMATCH", "REFLECTION_ADMISSION_UNAUTHENTICATED",
    "DUPLICATE_REFLECTION_ADMISSION", "DUPLICATE_REFLECTION_LEASE",
    "REFLECTION_LEASE_UNAUTHENTICATED", "REFLECTION_LEASE_ALREADY_CONSUMED",
    "REFLECTION_LEASE_INVALIDATED", "REFLECTION_ROLE_MISMATCH",
    "REFLECTION_WRONG_PROCESS", "PROOF_UNRESOLVED",
)
_DOMAIN = b"CATTUS:SYNTH.REFLECT.LIFECYCLE.PINNED.1:exact-reflection-lease:v1"
_SECRET = secrets.token_bytes(32)
_ISSUER_PID = os.getpid()
_LOCK = Lock()
_FALSE_AUTHORITY = (
    "runtime_authority", "real_task_runtime_authority", "repository_write_authority",
    "apply_authority", "network_authority", "host_mount_authority", "shell_authority",
    "arbitrary_java_authority", "arbitrary_reflection_authority", "arbitrary_class_authority",
    "arbitrary_method_authority", "private_method_authority", "field_write_authority",
    "enumeration_authority", "executor_authority", "BANK_authority", "compilation_authority",
    "constructor_reflection_authority", "arbitrary_class_loading_authority",
    "arbitrary_source_authority", "repository_java_authority", "arbitrary_command_authority",
    "generic_reflection_authority",
)


class PinnedSyntheticReflectionExecutionLeaseError(ValueError):
    def __init__(self, code, reason="", *, upstream_code=None, upstream_reason=None):
        self.code, self.reason = code, reason or code
        self.category = code
        self.upstream_code, self.upstream_reason = upstream_code, upstream_reason
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise PinnedSyntheticReflectionExecutionLeaseError(code, reason)


def _canonical(value):
    def exact(item):
        if type(item) in (str, int, bool, type(None)):
            return
        if type(item) is list:
            for child in item:
                exact(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                exact(child)
            return
        raise TypeError("exact canonical primitive/nested types required")
    exact(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _framed(value, role):
    if type(role) is not str or role not in (
            "lease-evidence", "lease-fingerprint", "lease-record-hmac"):
        raise ValueError("unknown pinned reflection lifecycle authentication role")
    return _DOMAIN + b"\x00" + role.encode("utf-8") + b"\x00" + _canonical(value).encode("utf-8")


def _digest(value, role):
    return sha256(_framed(value, role)).hexdigest()


def _sign(projection_json, state):
    return hmac.new(_SECRET, _framed({"immutable_issuance_projection": projection_json,
        "current_state": state}, "lease-record-hmac"), "sha256").hexdigest()


def _hex_id(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is tuple:
        return len(actual) == len(expected) and all(_exact(a, b) for a, b in zip(actual, expected))
    return type(expected) in (str, int, bool) and actual == expected


def _local_lock(*originals):
    # Reject a foreign process before waiting on a potentially inherited lock.
    pid = os.getpid()
    if type(pid) is not int or pid != _ISSUER_PID:
        _fail("REFLECTION_WRONG_PROCESS", "issuing owner process required")
    for original in originals:
        if type(original) is reflection_owner.SyntheticReflectionRequest:
            original_pid = getattr(original, "issuer_process_id", None)
        elif type(original) in (PinnedSyntheticReflectionExecutionLease,
                admission_owner.PinnedSyntheticReflectionExecutionAdmission,
                authorization_owner.PinnedSyntheticRuntimeAuthorization,
                runtime_owner.PinnedSyntheticRuntimeExecutionLease):
            original_pid = getattr(original, "issuing_pid", None)
        else:
            continue
        if type(original_pid) is not int or original_pid != _ISSUER_PID:
            _fail("REFLECTION_WRONG_PROCESS", "exact original issuing PID required")
    return _LOCK


def _upstream_failure(error, boundary):
    code = getattr(error, "code", getattr(error, "status", None))
    reason = getattr(error, "reason", str(error))
    category = code if type(code) is str and code in ERROR_CODES else "PROOF_UNRESOLVED"
    if code == "pinned_synthetic_authorization_unauthenticated":
        category = "PINNED_AUTH_UNAUTHENTICATED"
    elif code == "pinned_synthetic_authorization_scope_mismatch":
        category = "PINNED_AUTH_SCOPE_MISMATCH"
    elif code in ("pinned_provider_original_outcome_required", "pinned_provider_original_binding_required",
            "pinned_provider_incomplete", "pinned_provider_proof_only_required",
            "pinned_provider_exact_requirement_required", "pinned_synthetic_provider_graph_mismatch",
            "PINNED_BACKEND_BINDING_MISMATCH", "PINNED_RUNTIME_EVIDENCE_MISMATCH",
            "PINNED_CONTROLLER_MISMATCH", "PINNED_CLEANUP_FAILURE"):
        category = "PINNED_PROVIDER_PROVENANCE_MISMATCH"
    elif code == "LEASE_WRONG_PROCESS":
        category = "REFLECTION_WRONG_PROCESS"
    elif boundary == "runtime" and code in ("LEASE_ALREADY_CONSUMED", "LEASE_INVALIDATED", "LEASE_NOT_ISSUED"):
        category = "PINNED_RUNTIME_STATE_MISMATCH"
    elif boundary == "runtime" and code == "LEASE_UNAUTHENTICATED":
        category = "PINNED_RUNTIME_LEASE_UNAUTHENTICATED"
    elif boundary == "request" and code == "synthetic_reflection_unauthenticated":
        category = "REFLECTION_REQUEST_UNAUTHENTICATED"
    elif boundary == "request" and code in ("synthetic_reflection_scope_mismatch", "synthetic_definition_mismatch"):
        category = "REFLECTION_SCOPE_MISMATCH"
    raise PinnedSyntheticReflectionExecutionLeaseError(category, str(reason),
        upstream_code=code, upstream_reason=reason) from error


def _public_validate(value, exact_class, validator, boundary, **kwargs):
    category = {"admission": "REFLECTION_ADMISSION_UNAUTHENTICATED",
        "request": "REFLECTION_REQUEST_UNAUTHENTICATED", "authorization": "PINNED_AUTH_UNAUTHENTICATED",
        "runtime": "PINNED_RUNTIME_LEASE_UNAUTHENTICATED"}[boundary]
    if type(value) is not exact_class:
        _fail(category, "exact original typed upstream required")
    try:
        original = validator(value, **kwargs)
    except Exception as error:
        _upstream_failure(error, boundary)
    if original is not value:
        _fail(category, "public validator must return the same original object")
    return original


def _fingerprint(value, boundary):
    try:
        fingerprint = value.fingerprint
    except Exception as error:
        _upstream_failure(error, boundary)
    if not _hex_id(fingerprint):
        _fail("PROOF_UNRESOLVED", "exact authenticated upstream fingerprint required")
    return fingerprint


def _runtime_state(runtime, authorization):
    try:
        state = runtime_owner.pinned_synthetic_runtime_execution_lease_state(
            runtime, authorization=authorization)
    except Exception as error:
        _upstream_failure(error, "runtime")
    if type(state) is not str or state not in (ISSUED, CONSUMED, INVALIDATED):
        _fail("PROOF_UNRESOLVED", "authenticated exact runtime current state unavailable")
    return state


def _semantic_role(request, role):
    if type(role) is not str or role not in (BEFORE, AFTER):
        _fail("REFLECTION_ROLE_MISMATCH", "exact semantic BEFORE or AFTER required")
    literal = BEFORE_ROLE if role == BEFORE else AFTER_ROLE
    if not _exact(getattr(request, "observation_role", None), literal):
        _fail("REFLECTION_ROLE_MISMATCH", "semantic role must match exact request role literal")
    return literal


def _fixed_scope(role):
    return {"semantic_role": role,
        "exact_request_observation_role": BEFORE_ROLE if role == BEFORE else AFTER_ROLE,
        "scenario_phase_id": SCENARIO_PHASE_ID, "scenario_id": SCENARIO_ID,
        "source_kind": SOURCE_KIND, "source_sha256": SOURCE_SHA256,
        "source_size_bytes": SOURCE_SIZE_BYTES, "definition_sha256": DEFINITION_SHA256,
        "class_name": "SyntheticStateBox", "method_name": "decrement",
        "method_signature": "boolean SyntheticStateBox.decrement(int)",
        "arguments": (3,), "argument_types": ("int",), "return_type": "boolean",
        "field_owner": "SyntheticStateBox", "field_name": "value", "field_type": "int",
        "operation": "read_exact_bound_field"}


def _verify_scope(admission, authorization, runtime, request, role):
    literal = _semantic_role(request, role)
    if (not _exact(getattr(admission, "semantic_role", None), role)
            or not _exact(getattr(admission, "exact_request_observation_role", None), literal)):
        _fail("REFLECTION_ROLE_MISMATCH", "admission and exact request role must agree")
    expected_request = {"schema_version": RENDERER_SCHEMA, "phase_id": SCENARIO_PHASE_ID,
        "scenario_id": SCENARIO_ID, "source_kind": SOURCE_KIND, "source_sha256": SOURCE_SHA256,
        "definition_sha256": DEFINITION_SHA256, "owner": "SyntheticStateBox", "member": "value",
        "declared_type": "int", "operation": "read_exact_bound_field", "observation_role": literal,
        "reflection_request_valid": True, "reflection_execution_authority": False,
        "runtime_authority": False, "real_task_runtime_authority": False,
        "repository_write_authority": False, "apply_authority": False, "field_write_authority": False,
        "enumeration_authority": False, "private_method_authority": False, "execution_ready": False}
    if any(not _exact(getattr(request, name, None), value) for name, value in expected_request.items()):
        _fail("REFLECTION_SCOPE_MISMATCH", "exact frozen request read scope required")
    scope = _fixed_scope(role)
    if any(not _exact(getattr(admission, name, None), value) for name, value in scope.items()):
        _fail("REFLECTION_SCOPE_MISMATCH", "exact admission scenario/source/invocation/field/read required")
    scenario_expected = {name: value for name, value in scope.items() if name not in (
        "semantic_role", "exact_request_observation_role", "scenario_phase_id", "source_kind", "operation")}
    scenario_expected.update(expected_before=10, expected_return=True, expected_after=7)
    for upstream, owner, phase, schema in (
            (authorization, "core.synthetic_runtime_authorization_pinned", "SYNTH.AUTH.PINNED.1",
                "synthetic_runtime_authorization_pinned_1_v1"),
            (runtime, "core.synthetic_runtime_authorization_pinned_lifecycle", "SYNTH.AUTH.LIFECYCLE.PINNED.1",
                "synthetic_runtime_execution_lease_pinned_1_v1")):
        epoch = {"owner_identity": owner, "phase_id": phase, "schema_version": schema, "issuing_pid": _ISSUER_PID}
        if any(not _exact(getattr(upstream, name, None), value) for name, value in epoch.items()):
            _fail("REFLECTION_SCOPE_MISMATCH", "exact authenticated pinned owner epoch required")
        scenario = getattr(upstream, "scenario", None)
        if type(scenario) is not authorization_owner.PinnedSyntheticScenarioIdentity or any(
                not _exact(getattr(scenario, name, None), value) for name, value in scenario_expected.items()):
            _fail("REFLECTION_SCOPE_MISMATCH", "exact frozen scenario/source/invocation/field required")
    admission_epoch = {"owner_identity": "core.synthetic_reflection_execution_admission_pinned",
        "phase_id": "SYNTH.REFLECT.ADMIT.PINNED.1",
        "schema_version": "synthetic_reflection_execution_admission_pinned_1_v1",
        "issuing_pid": _ISSUER_PID, "runtime_state_at_issuance": ISSUED,
        "renderer_identity": RENDERER_IDENTITY, "renderer_phase": RENDERER_PHASE,
        "renderer_schema_version": RENDERER_SCHEMA,
        "renderer_helper_sha256": BEFORE_HELPER_SHA256 if role == BEFORE else AFTER_HELPER_SHA256}
    if any(not _exact(getattr(admission, name, None), value) for name, value in admission_epoch.items()):
        _fail("REFLECTION_SCOPE_MISMATCH", "exact admission owner and renderer evidence required")
    if (not _exact(runtime.scenario_phase_id, SCENARIO_PHASE_ID)
            or not _exact(runtime.source_kind, SOURCE_KIND)):
        _fail("REFLECTION_SCOPE_MISMATCH", "exact runtime scenario phase and source kind required")
    for value in (admission.admission_id, authorization.authorization_id,
            authorization.proof_context_id, runtime.lease_id, request.issuance_id):
        if not _hex_id(value):
            _fail("PROOF_UNRESOLVED", "exact authenticated original issuance identifiers required")


def _authenticate_graph(admission, authorization, runtime, request, role, *, require_issued=False):
    # The first admission check authenticates before any one-shot key is derived.
    _public_validate(admission, admission_owner.PinnedSyntheticReflectionExecutionAdmission,
        admission_owner.validate_pinned_synthetic_reflection_execution_admission, "admission")
    _public_validate(request, reflection_owner.SyntheticReflectionRequest,
        reflection_owner.validate_synthetic_reflection_request, "request")
    _public_validate(authorization, authorization_owner.PinnedSyntheticRuntimeAuthorization,
        authorization_owner.validate_pinned_synthetic_runtime_authorization, "authorization")
    _public_validate(runtime, runtime_owner.PinnedSyntheticRuntimeExecutionLease,
        runtime_owner.validate_pinned_synthetic_runtime_execution_lease, "runtime", authorization=authorization)
    state = _runtime_state(runtime, authorization)
    if require_issued and state != ISSUED:
        _fail("PINNED_RUNTIME_STATE_MISMATCH", "both reflection lease roles require runtime ISSUED")
    _verify_scope(admission, authorization, runtime, request, role)
    # Only the unchanged public admission owner can authenticate retained identity.
    _public_validate(admission, admission_owner.PinnedSyntheticReflectionExecutionAdmission,
        admission_owner.validate_pinned_synthetic_reflection_execution_admission, "admission",
        authorization=authorization, runtime=runtime, request=request, role=role)
    graph = {"admission_fingerprint": _fingerprint(admission, "admission"),
        "authorization_fingerprint": _fingerprint(authorization, "authorization"),
        "runtime_lease_fingerprint": _fingerprint(runtime, "runtime"),
        "request_fingerprint": _fingerprint(request, "request")}
    expected_runtime = {"authorization_id": authorization.authorization_id,
        "authorization_fingerprint": graph["authorization_fingerprint"],
        "authorization_proof_context_id": authorization.proof_context_id}
    if any(not _exact(getattr(runtime, name, None), value) for name, value in expected_runtime.items()):
        _fail("PINNED_AUTH_SCOPE_MISMATCH", "runtime must bind the exact original authorization graph")
    expected_admission = {**expected_runtime,
        "authorization_owner_identity": authorization.owner_identity,
        "authorization_phase_id": authorization.phase_id,
        "authorization_schema_version": authorization.schema_version,
        "authorization_issuing_pid": authorization.issuing_pid,
        "runtime_owner_identity": runtime.owner_identity, "runtime_phase_id": runtime.phase_id,
        "runtime_schema_version": runtime.schema_version, "runtime_issuing_pid": runtime.issuing_pid,
        "runtime_lease_id": runtime.lease_id, "runtime_lease_fingerprint": graph["runtime_lease_fingerprint"],
        "request_issuance_id": request.issuance_id, "request_issuing_pid": request.issuer_process_id,
        "request_fingerprint": graph["request_fingerprint"]}
    if any(not _exact(getattr(admission, name, None), value) for name, value in expected_admission.items()):
        _fail("REFLECTION_SCOPE_MISMATCH", "admission must bind the supplied original graph and exact scope")
    if not _hex_id(admission.renderer_fingerprint):
        _fail("PROOF_UNRESOLVED", "authenticated retained renderer fingerprint required")
    return state, graph


def _one_shot_key(admission):
    # The original is publicly authenticated first and strongly retained forever.
    return (admission.owner_identity, admission.phase_id, admission.schema_version,
        admission.issuing_pid, admission.admission_id)


class _LocalLease:
    __slots__ = ("__weakref__",)


@dataclass(frozen=True, slots=True)
class PinnedSyntheticReflectionExecutionLease(_LocalLease):
    lease_id: str
    issuing_pid: int
    semantic_role: str
    exact_request_observation_role: str
    admission_owner_identity: str
    admission_phase_id: str
    admission_schema_version: str
    admission_issuing_pid: int
    admission_id: str
    admission_fingerprint: str
    authorization_owner_identity: str
    authorization_phase_id: str
    authorization_schema_version: str
    authorization_issuing_pid: int
    authorization_id: str
    authorization_fingerprint: str
    authorization_proof_context_id: str
    runtime_owner_identity: str
    runtime_phase_id: str
    runtime_schema_version: str
    runtime_issuing_pid: int
    runtime_lease_id: str
    runtime_lease_fingerprint: str
    request_issuance_id: str
    request_issuing_pid: int
    request_fingerprint: str
    renderer_helper_sha256: str
    renderer_fingerprint: str
    evidence_digest: str
    stable_fingerprint: str
    owner_identity: str = field(default=OWNER_ID, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    initial_state: str = field(default=ISSUED, init=False)
    runtime_state_at_issuance: str = field(default=ISSUED, init=False)
    scenario_phase_id: str = field(default=SCENARIO_PHASE_ID, init=False)
    scenario_id: str = field(default=SCENARIO_ID, init=False)
    source_kind: str = field(default=SOURCE_KIND, init=False)
    source_sha256: str = field(default=SOURCE_SHA256, init=False)
    source_size_bytes: int = field(default=SOURCE_SIZE_BYTES, init=False)
    definition_sha256: str = field(default=DEFINITION_SHA256, init=False)
    class_name: str = field(default="SyntheticStateBox", init=False)
    method_name: str = field(default="decrement", init=False)
    method_signature: str = field(default="boolean SyntheticStateBox.decrement(int)", init=False)
    arguments: tuple[int, ...] = field(default=(3,), init=False)
    argument_types: tuple[str, ...] = field(default=("int",), init=False)
    return_type: str = field(default="boolean", init=False)
    field_owner: str = field(default="SyntheticStateBox", init=False)
    field_name: str = field(default="value", init=False)
    field_type: str = field(default="int", init=False)
    operation: str = field(default="read_exact_bound_field", init=False)
    renderer_identity: str = field(default=RENDERER_IDENTITY, init=False)
    renderer_phase: str = field(default=RENDERER_PHASE, init=False)
    renderer_schema_version: str = field(default=RENDERER_SCHEMA, init=False)
    lease_issued: bool = field(default=True, init=False)
    exact_role_read_only_permission: bool = field(default=True, init=False)
    one_shot_exact_role_read_only_permission: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)
    shell_authority: bool = field(default=False, init=False)
    arbitrary_java_authority: bool = field(default=False, init=False)
    arbitrary_reflection_authority: bool = field(default=False, init=False)
    arbitrary_class_authority: bool = field(default=False, init=False)
    arbitrary_method_authority: bool = field(default=False, init=False)
    private_method_authority: bool = field(default=False, init=False)
    field_write_authority: bool = field(default=False, init=False)
    enumeration_authority: bool = field(default=False, init=False)
    executor_authority: bool = field(default=False, init=False)
    BANK_authority: bool = field(default=False, init=False)
    compilation_authority: bool = field(default=False, init=False)
    constructor_reflection_authority: bool = field(default=False, init=False)
    arbitrary_class_loading_authority: bool = field(default=False, init=False)
    arbitrary_source_authority: bool = field(default=False, init=False)
    repository_java_authority: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    generic_reflection_authority: bool = field(default=False, init=False)
    consumption_proves_reflection_read: bool = field(default=False, init=False)
    runtime_consumption_proves_invocation: bool = field(default=False, init=False)
    behavioral_activation_ready: bool = field(default=False, init=False)
    behavioral_readiness_reason: str = field(default="PROOF_UNRESOLVED", init=False)

    @property
    def fingerprint(self):
        return pinned_synthetic_reflection_execution_lease_fingerprint(self)

    @property
    def lifecycle_state(self):
        return pinned_synthetic_reflection_execution_lease_state(self)

    def as_dict(self):
        with _local_lock(self):
            record, runtime_state = _authenticated_record_locked(self)
            return {**_projection(self), "current_state": record.lifecycle_state,
                "runtime_current_state": runtime_state, "report_only": True}


@dataclass(frozen=True, slots=True)
class PinnedSyntheticReflectionExecutionLeaseReadiness:
    local_ready: bool
    reflection_active_ready: bool
    current_state: str
    runtime_current_state: str
    readiness_reason: str
    reason: str = field(default="PROOF_UNRESOLVED", init=False)
    behavioral_activation_ready: bool = field(default=False, init=False)
    report_only: bool = field(default=True, init=False)


@dataclass(frozen=True, slots=True)
class _LeaseRecord:
    admission: admission_owner.PinnedSyntheticReflectionExecutionAdmission
    authorization: authorization_owner.PinnedSyntheticRuntimeAuthorization
    runtime: runtime_owner.PinnedSyntheticRuntimeExecutionLease
    request: reflection_owner.SyntheticReflectionRequest
    lease_ref: ref
    projection_json: str
    lifecycle_state: str
    signature: str


@dataclass(frozen=True, slots=True)
class _OwnerStore:
    admission_leases: dict
    leases: dict


_STORE = _OwnerStore({}, {})


def _projection(lease):
    projection = {}
    for descriptor in fields(PinnedSyntheticReflectionExecutionLease):
        value = getattr(lease, descriptor.name, None)
        if descriptor.name in ("arguments", "argument_types"):
            expected = (3,) if descriptor.name == "arguments" else ("int",)
            if not _exact(value, expected):
                _fail("REFLECTION_SCOPE_MISMATCH", "exact immutable invocation element types required")
            value = list(value)
        elif descriptor.name in ("issuing_pid", "admission_issuing_pid", "authorization_issuing_pid",
                "runtime_issuing_pid", "request_issuing_pid"):
            if not _exact(value, _ISSUER_PID):
                _fail("REFLECTION_LEASE_UNAUTHENTICATED", "exact original process binding required")
        elif descriptor.name == "source_size_bytes":
            if not _exact(value, SOURCE_SIZE_BYTES):
                _fail("REFLECTION_SCOPE_MISMATCH", "exact frozen source size required")
        elif descriptor.name in _FALSE_AUTHORITY or descriptor.name in (
                "lease_issued", "exact_role_read_only_permission", "one_shot_exact_role_read_only_permission",
                "consumption_proves_reflection_read", "runtime_consumption_proves_invocation",
                "behavioral_activation_ready"):
            expected = descriptor.name in (
                "lease_issued", "exact_role_read_only_permission", "one_shot_exact_role_read_only_permission")
            if type(value) is not bool or value is not expected:
                _fail("REFLECTION_SCOPE_MISMATCH", "exact immutable authority and evidence matrix required")
        elif type(value) is not str:
            _fail("REFLECTION_LEASE_UNAUTHENTICATED", "exact lease string field required")
        projection[descriptor.name] = value
    return projection


def _new_lease(admission, authorization, runtime, request, role, graph, lease_id):
    lease = PinnedSyntheticReflectionExecutionLease(
        lease_id, _ISSUER_PID, role, _semantic_role(request, role),
        admission.owner_identity, admission.phase_id, admission.schema_version,
        admission.issuing_pid, admission.admission_id, graph["admission_fingerprint"],
        authorization.owner_identity, authorization.phase_id, authorization.schema_version,
        authorization.issuing_pid, authorization.authorization_id,
        graph["authorization_fingerprint"], authorization.proof_context_id,
        runtime.owner_identity, runtime.phase_id, runtime.schema_version, runtime.issuing_pid,
        runtime.lease_id, graph["runtime_lease_fingerprint"], request.issuance_id,
        request.issuer_process_id, graph["request_fingerprint"], admission.renderer_helper_sha256,
        admission.renderer_fingerprint, "", "")
    payload = _projection(lease)
    payload.pop("evidence_digest")
    payload.pop("stable_fingerprint")
    lease = replace(lease, evidence_digest=_digest(payload, "lease-evidence"))
    payload = _projection(lease)
    payload.pop("stable_fingerprint")
    return replace(lease, stable_fingerprint=_digest(payload, "lease-fingerprint"))


def _authenticated_record_locked(lease, admission=None, authorization=None, runtime=None, request=None, role=None):
    if type(lease) is not PinnedSyntheticReflectionExecutionLease or not _hex_id(getattr(lease, "lease_id", None)):
        _fail("REFLECTION_LEASE_UNAUTHENTICATED", "exact original live pinned reflection lease required")
    record = _STORE.leases.get(lease.lease_id)
    if type(record) is not _LeaseRecord or type(record.lease_ref) is not ref or record.lease_ref() is not lease:
        _fail("REFLECTION_LEASE_UNAUTHENTICATED", "independent live owner identity required")
    for supplied, retained in ((admission, record.admission), (authorization, record.authorization),
            (runtime, record.runtime), (request, record.request)):
        if supplied is not None and supplied is not retained:
            _fail("REFLECTION_LEASE_UNAUTHENTICATED", "supplied upstream must be the retained exact original")
    retained_role = lease.semantic_role
    if role is not None and (type(role) is not str or role != retained_role):
        _fail("REFLECTION_ROLE_MISMATCH", "supplied semantic role must equal retained role")
    runtime_state, graph = _authenticate_graph(record.admission, record.authorization,
        record.runtime, record.request, retained_role)
    if _STORE.admission_leases.get(_one_shot_key(record.admission)) != lease.lease_id:
        _fail("REFLECTION_LEASE_UNAUTHENTICATED", "permanent original admission binding required")
    payload = _projection(lease)
    expected = _new_lease(record.admission, record.authorization, record.runtime,
        record.request, retained_role, graph, lease.lease_id)
    if _canonical(payload) != _canonical(_projection(expected)):
        _fail("REFLECTION_SCOPE_MISMATCH", "immutable exact original graph and lease projection required")
    if (type(record.projection_json) is not str or _canonical(payload) != record.projection_json
            or type(record.lifecycle_state) is not str or record.lifecycle_state not in (ISSUED, CONSUMED, INVALIDATED)
            or not _hex_id(record.signature)
            or not hmac.compare_digest(record.signature, _sign(record.projection_json, record.lifecycle_state))):
        _fail("REFLECTION_LEASE_UNAUTHENTICATED", "private authenticated immutable issuance and current state required")
    return record, runtime_state


def issue_pinned_synthetic_reflection_execution_lease(admission, authorization, runtime, request, role):
    """Prepare one permanent exact read permission while runtime is ISSUED."""
    global _STORE
    with _local_lock(admission, authorization, runtime, request):
        _, graph = _authenticate_graph(admission, authorization, runtime, request, role, require_issued=True)
        key = _one_shot_key(admission)
        if key in _STORE.admission_leases:
            _fail("DUPLICATE_REFLECTION_LEASE", "admission already has a permanent lease tombstone")
        lease_id = secrets.token_hex(32)
        if not _hex_id(lease_id):
            _fail("PROOF_UNRESOLVED", "owner lease identifier unavailable")
        while lease_id in _STORE.leases:
            lease_id = secrets.token_hex(32)
            if not _hex_id(lease_id):
                _fail("PROOF_UNRESOLVED", "owner lease identifier unavailable")
        lease = _new_lease(admission, authorization, runtime, request, role, graph, lease_id)
        projection_json = _canonical(_projection(lease))
        record = _LeaseRecord(admission, authorization, runtime, request, ref(lease),
            projection_json, ISSUED, _sign(projection_json, ISSUED))
        updated = _OwnerStore({**_STORE.admission_leases, key: lease_id}, {**_STORE.leases, lease_id: record})
        # Last authenticated runtime eligibility point; no upstream private lock.
        if _runtime_state(runtime, authorization) != ISSUED:
            _fail("PINNED_RUNTIME_STATE_MISMATCH", "runtime changed before reflection lease publication")
        _STORE = updated  # The only issuance publication/linearization point.
        return lease


def validate_pinned_synthetic_reflection_execution_lease(
        lease, admission=None, authorization=None, runtime=None, request=None, role=None):
    """Authenticate all originals and current state, including terminal evidence."""
    with _local_lock(lease, admission, authorization, runtime, request):
        _authenticated_record_locked(lease, admission, authorization, runtime, request, role)
        return lease


def pinned_synthetic_reflection_execution_lease_fingerprint(
        lease, admission=None, authorization=None, runtime=None, request=None, role=None):
    """Return issuance identity, independent of mutable reflection current state."""
    with _local_lock(lease, admission, authorization, runtime, request):
        _authenticated_record_locked(lease, admission, authorization, runtime, request, role)
        return lease.stable_fingerprint


def pinned_synthetic_reflection_execution_lease_state(
        lease, admission=None, authorization=None, runtime=None, request=None, role=None):
    with _local_lock(lease, admission, authorization, runtime, request):
        record, _ = _authenticated_record_locked(lease, admission, authorization, runtime, request, role)
        return record.lifecycle_state


def _readiness(lease, admission, authorization, runtime, request, role, required_runtime):
    with _local_lock(lease, admission, authorization, runtime, request):
        record, runtime_state = _authenticated_record_locked(
            lease, admission, authorization, runtime, request, role)
        if record.lifecycle_state != ISSUED:
            readiness_reason = ("REFLECTION_LEASE_ALREADY_CONSUMED" if record.lifecycle_state == CONSUMED
                else "REFLECTION_LEASE_INVALIDATED")
        elif runtime_state != required_runtime:
            readiness_reason = "PINNED_RUNTIME_STATE_MISMATCH"
        else:
            readiness_reason = "PROOF_UNRESOLVED"
        return PinnedSyntheticReflectionExecutionLeaseReadiness(
            record.lifecycle_state == ISSUED and runtime_state == ISSUED,
            record.lifecycle_state == ISSUED and runtime_state == CONSUMED,
            record.lifecycle_state, runtime_state, readiness_reason)


def check_pinned_synthetic_reflection_execution_lease_preexecution_readiness(
        lease, admission=None, authorization=None, runtime=None, request=None, role=None):
    """Immutable local readiness report; unresolved behavioral gates stay false."""
    return _readiness(lease, admission, authorization, runtime, request, role, ISSUED)


def check_pinned_synthetic_reflection_execution_lease_active_readiness(
        lease, admission=None, authorization=None, runtime=None, request=None, role=None):
    """Immutable active readiness report; caller booleans cannot grant authority."""
    return _readiness(lease, admission, authorization, runtime, request, role, CONSUMED)


def _transition(lease, admission, authorization, runtime, request, role, target):
    global _STORE
    with _local_lock(lease, admission, authorization, runtime, request):
        record, runtime_state = _authenticated_record_locked(
            lease, admission, authorization, runtime, request, role)
        if type(target) is not str or target not in (CONSUMED, INVALIDATED):
            _fail("REFLECTION_LEASE_UNAUTHENTICATED", "unsupported terminal transition")
        if record.lifecycle_state != ISSUED:
            _fail("REFLECTION_LEASE_ALREADY_CONSUMED" if record.lifecycle_state == CONSUMED
                else "REFLECTION_LEASE_INVALIDATED", "reflection terminal state cannot transition")
        if target == CONSUMED and runtime_state != CONSUMED:
            _fail("PINNED_RUNTIME_STATE_MISMATCH", "reflection consume requires authenticated runtime CONSUMED")
        updated_record = replace(record, lifecycle_state=target, signature=_sign(record.projection_json, target))
        updated = _OwnerStore(_STORE.admission_leases, {**_STORE.leases, lease.lease_id: updated_record})
        _STORE = updated  # The only terminal publication/linearization point.
        return lease


def consume_pinned_synthetic_reflection_execution_lease(
        lease, admission=None, authorization=None, runtime=None, request=None, role=None):
    """Spend exact permission only after runtime consumption; performs no read."""
    return _transition(lease, admission, authorization, runtime, request, role, CONSUMED)


def invalidate_pinned_synthetic_reflection_execution_lease(
        lease, admission=None, authorization=None, runtime=None, request=None, role=None):
    """Permanently abandon ISSUED permission in any authentic runtime state."""
    return _transition(lease, admission, authorization, runtime, request, role, INVALIDATED)
