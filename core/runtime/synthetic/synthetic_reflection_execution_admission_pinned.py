"""SYNTH.REFLECT.ADMIT.PINNED.1: additive exact reflection preparation evidence.

Only unchanged public request, pinned authorization and pinned runtime APIs
authenticate originals. Issuance publishes a permanent role slot atomically
inside this owner, after a final public runtime ISSUED eligibility snapshot.
There is no cross-owner transaction, reflection lifecycle, consumer or effect.
Renderer pins describe unchanged text; this owner never invokes the renderer.
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
from core.runtime.synthetic import synthetic_runtime_authorization_pinned as authorization_owner
from core.runtime.synthetic import synthetic_runtime_authorization_pinned_lifecycle as runtime_owner

OWNER_ID = "core.synthetic_reflection_execution_admission_pinned"
PHASE_ID = "SYNTH.REFLECT.ADMIT.PINNED.1"
SCHEMA_VERSION = "synthetic_reflection_execution_admission_pinned_1_v1"
COMPLETE = "SYNTH_REFLECT_ADMIT_PINNED_1A_COMPLETE"
SCENARIO_PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
SCENARIO_ID = "synthetic.EXECUTOR.1R.decrement_3"
SOURCE_KIND = "phase_owned_synthetic_fixture"
SOURCE_SHA256 = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
SOURCE_SIZE_BYTES = 239
DEFINITION_SHA256 = "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d"
BEFORE, AFTER = "BEFORE", "AFTER"
BEFORE_ROLE, AFTER_ROLE = "exact_private_state_before", "exact_private_state_after"
ISSUED = "ISSUED"
RENDERER_IDENTITY = "SYNTH.REFLECT.1.render_synthetic_read_only_reflection"
RENDERER_PHASE = "SYNTH.REFLECT.1"
RENDERER_SCHEMA = "synthetic_reflection_request_v1"
# SHA-256 of the unchanged public renderer's role-specific UTF-8 helper text.
# Pure source/AST tests verify these pins without invoking the renderer.
BEFORE_HELPER_SHA256 = "c88aeea914c88ef17a335a184abe6d5b618a9c0c70a7121621ba67edd9919531"
AFTER_HELPER_SHA256 = "4d85951e886bfedabae50c7f64e8e0fa4985e8fa515e4edab9af0a355b10f4ea"
ERROR_CODES = (
    "PINNED_AUTH_UNAUTHENTICATED", "PINNED_RUNTIME_LEASE_UNAUTHENTICATED",
    "PINNED_AUTH_SCOPE_MISMATCH", "PINNED_PROVIDER_PROVENANCE_MISMATCH",
    "PINNED_RUNTIME_STATE_MISMATCH", "REFLECTION_REQUEST_UNAUTHENTICATED",
    "REFLECTION_SCOPE_MISMATCH", "DUPLICATE_REFLECTION_ADMISSION",
    "REFLECTION_ADMISSION_UNAUTHENTICATED", "REFLECTION_ROLE_MISMATCH",
    "REFLECTION_WRONG_PROCESS", "PROOF_UNRESOLVED",
)
_DOMAIN = b"CATTUS:SYNTH.REFLECT.ADMIT.PINNED.1:exact-reflection-admission:v1"
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
)


class PinnedSyntheticReflectionExecutionAdmissionError(ValueError):
    def __init__(self, code, reason="", *, upstream_code=None, upstream_reason=None):
        self.code, self.reason = code, reason or code
        self.upstream_code, self.upstream_reason = upstream_code, upstream_reason
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise PinnedSyntheticReflectionExecutionAdmissionError(code, reason)


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
            "renderer-evidence", "admission-evidence", "admission-fingerprint", "admission-record-hmac"):
        raise ValueError("unknown admission authentication role")
    return _DOMAIN + b"\x00" + role.encode("utf-8") + b"\x00" + _canonical(value).encode("utf-8")


def _digest(value, role):
    return sha256(_framed(value, role)).hexdigest()


def _sign(projection_json):
    return hmac.new(_SECRET, _framed({"immutable_admission_projection": projection_json},
        "admission-record-hmac"), "sha256").hexdigest()


def _hex_id(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is tuple:
        return len(actual) == len(expected) and all(_exact(a, b) for a, b in zip(actual, expected))
    return type(expected) in (str, int, bool) and actual == expected


def _local_lock(*originals):
    # Reject a foreign process before it can wait on an inherited owner lock.
    pid = os.getpid()
    if type(pid) is not int or pid != _ISSUER_PID:
        _fail("REFLECTION_WRONG_PROCESS", "issuing owner process required")
    for original in originals:
        if type(original) is reflection_owner.SyntheticReflectionRequest:
            original_pid = getattr(original, "issuer_process_id", None)
        elif type(original) in (PinnedSyntheticReflectionExecutionAdmission,
                authorization_owner.PinnedSyntheticRuntimeAuthorization,
                runtime_owner.PinnedSyntheticRuntimeExecutionLease):
            original_pid = getattr(original, "issuing_pid", None)
        else:
            continue
        if original_pid is not None and (type(original_pid) is not int or original_pid != _ISSUER_PID):
            _fail("REFLECTION_WRONG_PROCESS", "exact original issuing PID required")
    return _LOCK


def _upstream_failure(error, boundary):
    code = getattr(error, "code", getattr(error, "status", None))
    reason = getattr(error, "reason", str(error))
    category = "PROOF_UNRESOLVED"
    if code in ("PINNED_AUTH_SCOPE_MISMATCH", "pinned_synthetic_authorization_scope_mismatch"):
        category = "PINNED_AUTH_SCOPE_MISMATCH"
    elif code in ("PINNED_PROVIDER_PROVENANCE_MISMATCH", "pinned_provider_original_outcome_required",
            "pinned_provider_original_binding_required", "pinned_provider_incomplete",
            "pinned_provider_proof_only_required", "pinned_provider_exact_requirement_required",
            "pinned_synthetic_provider_graph_mismatch", "PINNED_BACKEND_BINDING_MISMATCH",
            "PINNED_RUNTIME_EVIDENCE_MISMATCH", "PINNED_CONTROLLER_MISMATCH", "PINNED_CLEANUP_FAILURE"):
        category = "PINNED_PROVIDER_PROVENANCE_MISMATCH"
    elif code in ("PINNED_AUTH_UNAUTHENTICATED", "pinned_synthetic_authorization_unauthenticated"):
        category = "PINNED_AUTH_UNAUTHENTICATED"
    elif boundary == "runtime" and code in ("LEASE_ALREADY_CONSUMED", "LEASE_INVALIDATED", "LEASE_NOT_ISSUED"):
        category = "PINNED_RUNTIME_STATE_MISMATCH"
    elif boundary == "runtime" and code == "LEASE_UNAUTHENTICATED":
        category = "PINNED_RUNTIME_LEASE_UNAUTHENTICATED"
    elif code == "LEASE_WRONG_PROCESS":
        category = "REFLECTION_WRONG_PROCESS"
    elif boundary == "request" and code == "synthetic_reflection_unauthenticated":
        category = "REFLECTION_REQUEST_UNAUTHENTICATED"
    elif boundary == "request" and code in ("synthetic_reflection_scope_mismatch", "synthetic_definition_mismatch"):
        category = "REFLECTION_SCOPE_MISMATCH"
    raise PinnedSyntheticReflectionExecutionAdmissionError(category, str(reason),
        upstream_code=code, upstream_reason=reason) from error


def _public_validate(value, exact_class, validator, boundary, **kwargs):
    category = {"request": "REFLECTION_REQUEST_UNAUTHENTICATED",
        "authorization": "PINNED_AUTH_UNAUTHENTICATED",
        "runtime": "PINNED_RUNTIME_LEASE_UNAUTHENTICATED"}[boundary]
    if type(value) is not exact_class:
        _fail(category, "exact original typed upstream required")
    try:
        validated = validator(value, **kwargs)
    except Exception as error:
        _upstream_failure(error, boundary)
    if validated is not value:
        _fail(category, "public validator must return the same original object")
    return validated


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
    if type(state) is not str or state not in ("ISSUED", "CONSUMED", "INVALIDATED"):
        _fail("PROOF_UNRESOLVED", "authenticated exact runtime state unavailable")
    return state


def _semantic_role(request, role):
    if type(role) is not str or role not in (BEFORE, AFTER):
        _fail("REFLECTION_ROLE_MISMATCH", "exact semantic BEFORE or AFTER required")
    literal = BEFORE_ROLE if role == BEFORE else AFTER_ROLE
    if not _exact(getattr(request, "observation_role", None), literal):
        _fail("REFLECTION_ROLE_MISMATCH", "semantic role must match exact request role literal")
    return literal


def _fixed_scope(role):
    return {
        "semantic_role": role,
        "exact_request_observation_role": BEFORE_ROLE if role == BEFORE else AFTER_ROLE,
        "scenario_phase_id": SCENARIO_PHASE_ID, "scenario_id": SCENARIO_ID,
        "source_kind": SOURCE_KIND, "source_sha256": SOURCE_SHA256,
        "source_size_bytes": SOURCE_SIZE_BYTES, "definition_sha256": DEFINITION_SHA256,
        "class_name": "SyntheticStateBox", "method_name": "decrement",
        "method_signature": "boolean SyntheticStateBox.decrement(int)",
        "arguments": (3,), "argument_types": ("int",), "return_type": "boolean",
        "field_owner": "SyntheticStateBox", "field_name": "value", "field_type": "int",
        "operation": "read_exact_bound_field",
    }


def _verify_scope(authorization, runtime, request, role):
    literal = _semantic_role(request, role)
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
    scenario_expected = {name: value for name, value in scope.items() if name not in (
        "semantic_role", "exact_request_observation_role", "scenario_phase_id", "source_kind", "operation")}
    # Expectations remain scope data, never measurements or execution evidence.
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
    if (not _exact(runtime.scenario_phase_id, SCENARIO_PHASE_ID)
            or not _exact(runtime.source_kind, SOURCE_KIND)):
        _fail("REFLECTION_SCOPE_MISMATCH", "exact runtime scenario phase and source kind required")
    for value in (authorization.authorization_id, authorization.proof_context_id,
            runtime.lease_id, request.issuance_id):
        if not _hex_id(value):
            _fail("PROOF_UNRESOLVED", "exact authenticated issuance identifiers required")
    if not _exact(request.issuer_process_id, _ISSUER_PID):
        _fail("REFLECTION_WRONG_PROCESS", "exact request issuing PID required")


def _authenticate_graph(authorization, runtime, request, role, *, require_issued=False):
    request = _public_validate(request, reflection_owner.SyntheticReflectionRequest,
        reflection_owner.validate_synthetic_reflection_request, "request")
    authorization = _public_validate(authorization, authorization_owner.PinnedSyntheticRuntimeAuthorization,
        authorization_owner.validate_pinned_synthetic_runtime_authorization, "authorization")
    runtime = _public_validate(runtime, runtime_owner.PinnedSyntheticRuntimeExecutionLease,
        runtime_owner.validate_pinned_synthetic_runtime_execution_lease, "runtime", authorization=authorization)
    state = _runtime_state(runtime, authorization)
    if require_issued and state != ISSUED:
        _fail("PINNED_RUNTIME_STATE_MISMATCH", "both admission roles require runtime ISSUED")
    _verify_scope(authorization, runtime, request, role)
    auth_fingerprint = _fingerprint(authorization, "authorization")
    runtime_fingerprint = _fingerprint(runtime, "runtime")
    request_fingerprint = _fingerprint(request, "request")
    expected = {"authorization_id": authorization.authorization_id,
        "authorization_fingerprint": auth_fingerprint,
        "authorization_proof_context_id": authorization.proof_context_id}
    if any(not _exact(getattr(runtime, name, None), value) for name, value in expected.items()):
        _fail("PINNED_AUTH_SCOPE_MISMATCH", "runtime must bind the same exact authenticated authorization graph")
    return state, auth_fingerprint, runtime_fingerprint, request_fingerprint


def _one_shot_key(authorization, runtime, role):
    scope = _fixed_scope(role)
    return ((OWNER_ID, PHASE_ID, SCHEMA_VERSION, _ISSUER_PID),
        (authorization.owner_identity, authorization.phase_id, authorization.schema_version,
            authorization.issuing_pid, authorization.authorization_id),
        (runtime.owner_identity, runtime.phase_id, runtime.schema_version, runtime.issuing_pid, runtime.lease_id),
        role, tuple(scope.items()))


def _renderer_projection(role):
    return {"renderer_identity": RENDERER_IDENTITY, "renderer_phase": RENDERER_PHASE,
        "renderer_schema_version": RENDERER_SCHEMA,
        "fixed_helper_sha256": BEFORE_HELPER_SHA256 if role == BEFORE else AFTER_HELPER_SHA256}


class _LocalAdmission:
    __slots__ = ("__weakref__",)


@dataclass(frozen=True, slots=True)
class PinnedSyntheticReflectionExecutionAdmission(_LocalAdmission):
    admission_id: str
    issuing_pid: int
    semantic_role: str
    exact_request_observation_role: str
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
    exact_role_read_only_permission: bool = field(default=True, init=False)
    admission_can_prepare_lease_only: bool = field(default=True, init=False)
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
    behavioral_activation_ready: bool = field(default=False, init=False)
    behavioral_readiness_reason: str = field(default="PROOF_UNRESOLVED", init=False)

    @property
    def fingerprint(self):
        return pinned_synthetic_reflection_execution_admission_fingerprint(self)

    def as_dict(self):
        with _local_lock(self):
            _authenticated_record_locked(self)
            return {**_projection(self), "report_only": True}


@dataclass(frozen=True, slots=True)
class _AdmissionRecord:
    authorization: authorization_owner.PinnedSyntheticRuntimeAuthorization
    runtime: runtime_owner.PinnedSyntheticRuntimeExecutionLease
    request: reflection_owner.SyntheticReflectionRequest
    admission_ref: ref
    projection_json: str
    signature: str


@dataclass(frozen=True, slots=True)
class _OwnerStore:
    admission_slots: dict
    admissions: dict


_STORE = _OwnerStore({}, {})


def _projection(admission):
    projection = {}
    for descriptor in fields(PinnedSyntheticReflectionExecutionAdmission):
        value = getattr(admission, descriptor.name, None)
        if descriptor.name in ("arguments", "argument_types"):
            expected = (3,) if descriptor.name == "arguments" else ("int",)
            if not _exact(value, expected):
                _fail("REFLECTION_SCOPE_MISMATCH", "exact invocation element types required")
            value = list(value)
        elif descriptor.name in ("issuing_pid", "authorization_issuing_pid", "runtime_issuing_pid", "request_issuing_pid"):
            if not _exact(value, _ISSUER_PID):
                _fail("REFLECTION_ADMISSION_UNAUTHENTICATED", "exact original PID binding required")
        elif descriptor.name == "source_size_bytes":
            if not _exact(value, SOURCE_SIZE_BYTES):
                _fail("REFLECTION_SCOPE_MISMATCH", "exact source size required")
        elif descriptor.name in _FALSE_AUTHORITY or descriptor.name in (
                "exact_role_read_only_permission", "admission_can_prepare_lease_only", "behavioral_activation_ready"):
            expected = descriptor.name in ("exact_role_read_only_permission", "admission_can_prepare_lease_only")
            if type(value) is not bool or value is not expected:
                _fail("REFLECTION_SCOPE_MISMATCH", "immutable exact authority matrix required")
        elif type(value) is not str:
            _fail("REFLECTION_ADMISSION_UNAUTHENTICATED", "exact admission string field required")
        projection[descriptor.name] = value
    return projection


def _new_admission(authorization, runtime, request, role, graph, admission_id):
    _, auth_fingerprint, runtime_fingerprint, request_fingerprint = graph
    renderer = _renderer_projection(role)
    admission = PinnedSyntheticReflectionExecutionAdmission(
        admission_id, _ISSUER_PID, role, _semantic_role(request, role),
        authorization.owner_identity, authorization.phase_id, authorization.schema_version,
        authorization.issuing_pid, authorization.authorization_id, auth_fingerprint, authorization.proof_context_id,
        runtime.owner_identity, runtime.phase_id, runtime.schema_version, runtime.issuing_pid,
        runtime.lease_id, runtime_fingerprint, request.issuance_id, request.issuer_process_id, request_fingerprint,
        renderer["fixed_helper_sha256"], _digest(renderer, "renderer-evidence"), "", "")
    payload = _projection(admission)
    payload.pop("evidence_digest")
    payload.pop("stable_fingerprint")
    admission = replace(admission, evidence_digest=_digest(payload, "admission-evidence"))
    payload = _projection(admission)
    payload.pop("stable_fingerprint")
    return replace(admission, stable_fingerprint=_digest(payload, "admission-fingerprint"))


def _authenticated_record_locked(admission, authorization=None, runtime=None, request=None, role=None):
    if type(admission) is not PinnedSyntheticReflectionExecutionAdmission or not _hex_id(getattr(admission, "admission_id", None)):
        _fail("REFLECTION_ADMISSION_UNAUTHENTICATED", "exact original live admission required")
    record = _STORE.admissions.get(admission.admission_id)
    if type(record) is not _AdmissionRecord or type(record.admission_ref) is not ref or record.admission_ref() is not admission:
        _fail("REFLECTION_ADMISSION_UNAUTHENTICATED", "independent live owner identity required")
    for supplied, retained in ((authorization, record.authorization), (runtime, record.runtime), (request, record.request)):
        if supplied is not None and supplied is not retained:
            _fail("REFLECTION_ADMISSION_UNAUTHENTICATED", "supplied upstream must be the exact retained original")
    retained_role = admission.semantic_role
    if role is not None and (type(role) is not str or role != retained_role):
        _fail("REFLECTION_ROLE_MISMATCH", "supplied semantic role must equal retained role")
    graph = _authenticate_graph(record.authorization, record.runtime, record.request, retained_role)
    if _STORE.admission_slots.get(_one_shot_key(record.authorization, record.runtime, retained_role)) != admission.admission_id:
        _fail("REFLECTION_ADMISSION_UNAUTHENTICATED", "permanent exact runtime/role binding required")
    payload = _projection(admission)
    expected = _new_admission(record.authorization, record.runtime, record.request, retained_role, graph, admission.admission_id)
    if _canonical(payload) != _canonical(_projection(expected)):
        _fail("REFLECTION_SCOPE_MISMATCH", "immutable original graph and exact admission projection required")
    if (type(record.projection_json) is not str or _canonical(payload) != record.projection_json
            or not _hex_id(record.signature) or not hmac.compare_digest(record.signature, _sign(record.projection_json))):
        _fail("REFLECTION_ADMISSION_UNAUTHENTICATED", "independent private authenticated owner record required")
    return record


def issue_pinned_synthetic_reflection_execution_admission(authorization, runtime, request, role):
    """Prepare one permanent exact read role while runtime authenticates ISSUED."""
    global _STORE
    with _local_lock(authorization, runtime, request):
        graph = _authenticate_graph(authorization, runtime, request, role, require_issued=True)
        key = _one_shot_key(authorization, runtime, role)
        if key in _STORE.admission_slots:
            _fail("DUPLICATE_REFLECTION_ADMISSION", "permanent runtime/role slot already issued")
        admission_id = secrets.token_hex(32)
        if not _hex_id(admission_id):
            _fail("PROOF_UNRESOLVED", "owner admission identifier unavailable")
        while admission_id in _STORE.admissions:
            admission_id = secrets.token_hex(32)
            if not _hex_id(admission_id):
                _fail("PROOF_UNRESOLVED", "owner admission identifier unavailable")
        admission = _new_admission(authorization, runtime, request, role, graph, admission_id)
        projection_json = _canonical(_projection(admission))
        record = _AdmissionRecord(authorization, runtime, request, ref(admission), projection_json, _sign(projection_json))
        updated = _OwnerStore({**_STORE.admission_slots, key: admission_id}, {**_STORE.admissions, admission_id: record})
        # Final public authenticated eligibility point; no upstream private lock.
        if _runtime_state(runtime, authorization) != ISSUED:
            _fail("PINNED_RUNTIME_STATE_MISMATCH", "runtime changed before admission publication")
        _STORE = updated  # The only publication/linearization point.
        return admission


def validate_pinned_synthetic_reflection_execution_admission(admission, authorization=None, runtime=None, request=None, role=None):
    """Authenticate all retained originals, including after runtime termination."""
    with _local_lock(admission, authorization, runtime, request):
        _authenticated_record_locked(admission, authorization, runtime, request, role)
        return admission


def pinned_synthetic_reflection_execution_admission_fingerprint(admission):
    with _local_lock(admission):
        _authenticated_record_locked(admission)
        return admission.stable_fingerprint


def pinned_synthetic_reflection_request_satisfies_runtime(authorization, runtime, request, role):
    """Report compatibility in any authentic runtime state; grants no permission."""
    try:
        with _local_lock(authorization, runtime, request):
            _authenticate_graph(authorization, runtime, request, role)
            return True
    except PinnedSyntheticReflectionExecutionAdmissionError:
        return False


def pinned_synthetic_reflection_admission_satisfies_executor(admission, authorization, runtime, request, role):
    """Report ISSUED preparation compatibility, never behavioral readiness."""
    try:
        with _local_lock(admission, authorization, runtime, request):
            if authorization is None or runtime is None or request is None:
                _fail("REFLECTION_ADMISSION_UNAUTHENTICATED", "all exact original upstreams required")
            record = _authenticated_record_locked(admission, authorization, runtime, request, role)
            _semantic_role(record.request, role)
            return _runtime_state(record.runtime, record.authorization) == ISSUED
    except PinnedSyntheticReflectionExecutionAdmissionError:
        return False
