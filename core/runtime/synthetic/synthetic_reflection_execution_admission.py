"""SYNTH.REFLECT.ADMIT.1: exact process-local read-only reflection admission.

This owner only admits one of SYNTH.REFLECT.1's two authenticated requests
when they are compatible with a live SYNTH.AUTH.1 authorization. It does not
render Java, execute reflection, launch a process, create a sandbox, or consume
either upstream authorization. Each admission is permanently bound to one
role and to the exact live upstream issuance identities that it admits.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from hashlib import sha256
import hmac
import json
import os
import secrets
from weakref import WeakValueDictionary

from core.runtime.synthetic import synthetic_read_only_reflection as reflection_owner
from core.runtime.synthetic import synthetic_runtime_authorization as authorization_owner

PHASE_ID = "SYNTH.REFLECT.ADMIT.1"
SCHEMA_VERSION = "synthetic_reflection_execution_admission_v1"
SCENARIO_PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
SCENARIO_ID = "synthetic.EXECUTOR.1R.decrement_3"
SOURCE_SHA256 = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
DEFINITION_SHA256 = "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d"
SOURCE_KIND = "phase_owned_synthetic_fixture"
OWNER = "SyntheticStateBox"
MEMBER = "value"
DECLARED_TYPE = "int"
OPERATION = "read_exact_bound_field"
RENDERER_IDENTITY = "SYNTH.REFLECT.1.render_synthetic_read_only_reflection"
BEFORE_ROLE = "exact_private_state_before"
AFTER_ROLE = "exact_private_state_after"
SUPPORTED_ROLES = (BEFORE_ROLE, AFTER_ROLE)
ISSUED = "issued"
COMPLETE = "SYNTH_REFLECT_ADMIT_1_COMPLETE"
CONSUMPTION_POLICY = (
    "single_execution_use_in_executor_issuing_process_immediately_before_exact_read; "
    "no replay after success; failure before reflection effect may remain unconsumed"
)

_SECRET = secrets.token_bytes(32)
_ISSUER_PID = os.getpid()
_ISSUED_ADMISSIONS = WeakValueDictionary()


class SyntheticReflectionExecutionAdmissionError(ValueError):
    def __init__(self, code: str, reason: str = ""):
        self.code = code
        self.reason = reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code: str, reason: str = ""):
    raise SyntheticReflectionExecutionAdmissionError(code, reason)


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _local_process():
    if type(os.getpid()) is not int or os.getpid() != _ISSUER_PID:
        _fail("synthetic_reflection_admission_unauthenticated", "issuing process required")


def _hex_id(value) -> bool:
    return (type(value) is str and len(value) == 64
        and all(character in "0123456789abcdef" for character in value))


class _LocalAdmission:
    __slots__ = ("__weakref__",)


@dataclass(frozen=True, slots=True)
class SyntheticReflectionExecutionAdmission(_LocalAdmission):
    """Immutable, role-specific permission subordinate to a live SYNTH.AUTH.1."""

    scenario_phase_id: str
    scenario_id: str
    observation_role: str
    source_sha256: str
    definition_sha256: str
    owner: str
    member: str
    declared_type: str
    operation: str
    renderer_identity: str
    renderer_fingerprint: str
    synthetic_authorization_fingerprint: str
    synthetic_authorization_issuance_id: str
    reflection_request_fingerprint: str
    reflection_request_issuance_id: str
    admission_id: str
    issuing_process_id: int
    _signature: str = field(default="", repr=False, compare=False)
    issuer_phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    synthetic_reflection_execution_authority: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    field_write_authority: bool = field(default=False, init=False)
    enumeration_authority: bool = field(default=False, init=False)
    private_method_authority: bool = field(default=False, init=False)
    constructor_reflection_authority: bool = field(default=False, init=False)
    arbitrary_class_loading_authority: bool = field(default=False, init=False)
    single_execution_use: bool = field(default=True, init=False)
    consumption_state: str = field(default=ISSUED, init=False)

    @property
    def fingerprint(self) -> str:
        validate_synthetic_reflection_execution_admission(self)
        return _hash(_payload(self))

    def as_dict(self) -> dict:
        validate_synthetic_reflection_execution_admission(self)
        return {**_payload(self), "admission_fingerprint": self.fingerprint,
            "report_only": True}


def _payload(admission) -> dict:
    return {descriptor.name: object.__getattribute__(admission, descriptor.name)
        for descriptor in fields(SyntheticReflectionExecutionAdmission)
        if descriptor.name != "_signature"}


def _exact_immutable(actual, expected) -> bool:
    return (type(actual) is type(expected)
        and type(expected) in {str, int, bool}
        and actual == expected)


def _scope_values(role: str) -> dict:
    return {
        "scenario_phase_id": SCENARIO_PHASE_ID,
        "scenario_id": SCENARIO_ID,
        "observation_role": role,
        "source_sha256": SOURCE_SHA256,
        "definition_sha256": DEFINITION_SHA256,
        "owner": OWNER,
        "member": MEMBER,
        "declared_type": DECLARED_TYPE,
        "operation": OPERATION,
        "renderer_identity": RENDERER_IDENTITY,
        "issuer_phase_id": PHASE_ID,
        "schema_version": SCHEMA_VERSION,
        "synthetic_reflection_execution_authority": True,
        "runtime_authority": False,
        "real_task_runtime_authority": False,
        "repository_write_authority": False,
        "apply_authority": False,
        "field_write_authority": False,
        "enumeration_authority": False,
        "private_method_authority": False,
        "constructor_reflection_authority": False,
        "arbitrary_class_loading_authority": False,
        "single_execution_use": True,
        "consumption_state": ISSUED,
    }


def _unsigned_admission(*, role, authorization_fingerprint,
        authorization_issuance_id, request_fingerprint, request_issuance_id,
        renderer_fingerprint,
        admission_id, process_id):
    return SyntheticReflectionExecutionAdmission(
        SCENARIO_PHASE_ID, SCENARIO_ID, role, SOURCE_SHA256, DEFINITION_SHA256,
        OWNER, MEMBER, DECLARED_TYPE, OPERATION, RENDERER_IDENTITY,
        renderer_fingerprint, authorization_fingerprint,
        authorization_issuance_id, request_fingerprint, request_issuance_id,
        admission_id, process_id)


def _sign(admission) -> str:
    return hmac.new(_SECRET, _json(_payload(admission)).encode("utf-8"), "sha256").hexdigest()


def validate_synthetic_reflection_execution_admission(
        admission: SyntheticReflectionExecutionAdmission):
    """Authenticate a currently live admission in its issuing process."""
    _local_process()
    if type(admission) is not SyntheticReflectionExecutionAdmission:
        _fail("synthetic_reflection_admission_unauthenticated", "owner-issued typed handle required")
    try:
        payload = _payload(admission)
        signature = object.__getattribute__(admission, "_signature")
    except (AttributeError, TypeError, ValueError):
        _fail("synthetic_reflection_admission_unauthenticated", "complete issued handle required")
    role = payload.get("observation_role")
    if type(role) is not str or role not in SUPPORTED_ROLES:
        _fail("synthetic_reflection_admission_scope_mismatch", "one exact private-state role required")
    admission_id = payload.get("admission_id")
    if (not _hex_id(admission_id)
            or _ISSUED_ADMISSIONS.get(admission_id) is not admission
            or type(payload.get("issuing_process_id")) is not int
            or payload["issuing_process_id"] != _ISSUER_PID):
        _fail("synthetic_reflection_admission_unauthenticated", "live issuance identity required")
    expected = _scope_values(role)
    if any(not _exact_immutable(payload.get(name), value) for name, value in expected.items()):
        _fail("synthetic_reflection_admission_scope_mismatch", "fixed read-only target and authority projection required")
    for name in ("renderer_fingerprint", "synthetic_authorization_fingerprint", "synthetic_authorization_issuance_id",
            "reflection_request_fingerprint", "reflection_request_issuance_id"):
        if not _hex_id(payload.get(name)):
            _fail("synthetic_reflection_admission_scope_mismatch", "exact upstream identity binding required")
    if not _hex_id(signature) or not hmac.compare_digest(signature, _sign(admission)):
        _fail("synthetic_reflection_admission_unauthenticated", "independent process-local authentication required")
    return admission


def _validate_upstream_pair(authorization, reflection_request):
    """Call both public validators and require their exact SYNTH.1 compatibility."""
    try:
        request = reflection_owner.validate_synthetic_reflection_request(reflection_request)
        spec = authorization_owner.executor1r_decrement_3_spec()
        auth = authorization_owner.validate_synthetic_runtime_authorization(
            authorization, spec=spec,
            source=authorization_owner.get_executor1r_decrement_3_source())
        # The SYNTH.REFLECT.1 public compatibility predicate independently
        # revalidates both upstream objects and its complete reflection binding.
        if reflection_owner.synthetic_reflection_satisfies_authorization(request, auth) is not True:
            return None
        observation = spec.observation_contract
        metadata = observation.requested_field_metadata
        invocation = spec.invocation_contract
        rendered = reflection_owner.render_synthetic_read_only_reflection(request)
        if type(rendered) is not str:
            return None
        renderer_fingerprint = _hash({
            "renderer_identity": RENDERER_IDENTITY,
            "renderer_phase": reflection_owner.PHASE_ID,
            "renderer_schema_version": reflection_owner.SCHEMA_VERSION,
            "fixed_helper_sha256": sha256(rendered.encode("utf-8")).hexdigest(),
        })
        if not (
                auth.synthetic_runtime_authority is True
                and auth.runtime_authority is False
                and auth.real_task_runtime_authority is False
                and request.reflection_request_valid is True
                and request.reflection_execution_authority is False
                and request.phase_id == reflection_owner.SCENARIO_PHASE_ID == spec.phase_id == SCENARIO_PHASE_ID
                and request.scenario_id == auth.scenario_id == spec.scenario_id == SCENARIO_ID
                and request.source_sha256 == auth.source_sha256 == metadata.source_sha256 == SOURCE_SHA256
                and request.source_kind == auth.source_kind == spec.source_kind == SOURCE_KIND
                and (invocation.owner, invocation.public_method, invocation.arguments,
                    invocation.argument_types, invocation.return_type)
                    == (OWNER, "decrement", (3,), ("int",), "boolean")
                and (request.owner, request.member, request.declared_type,
                    request.definition_sha256, request.operation)
                    == (metadata.owner, metadata.member, metadata.declared_type,
                        metadata.definition_sha256, OPERATION)
                    == (OWNER, MEMBER, DECLARED_TYPE, DEFINITION_SHA256, OPERATION)
                and observation.roles == (BEFORE_ROLE, "direct_public_return", AFTER_ROLE)
                and observation.future_exact_reflection_required is True
                and observation.reflection_authority is False
                and auth.future_exact_reflection_required is True
                and auth.reflection_authority is False
                and auth.execution_ready is False
                and request.observation_role in SUPPORTED_ROLES):
            return None
        return auth, request, renderer_fingerprint
    except Exception:
        # Both validators are fail-closed. Treat any malformed, stale, foreign,
        # or unavailable upstream validation as an incompatible input.
        return None


def issue_synthetic_reflection_execution_admission(
        authorization: authorization_owner.SyntheticRuntimeAuthorization,
        reflection_request: reflection_owner.SyntheticReflectionRequest
        ) -> SyntheticReflectionExecutionAdmission:
    """Issue one admission for a validated request's exact role and identity."""
    _local_process()
    pair = _validate_upstream_pair(authorization, reflection_request)
    if pair is None:
        _fail("synthetic_reflection_admission_incompatible", "fresh exact SYNTH.AUTH.1 and SYNTH.REFLECT.1 handles required")
    auth, request, renderer_fingerprint = pair
    try:
        authorization_fingerprint = auth.fingerprint
        request_fingerprint = request.fingerprint
        role = request.observation_role
        authorization_issuance_id = auth.issuance_id
        request_issuance_id = request.issuance_id
    except Exception:
        _fail("synthetic_reflection_admission_incompatible", "authenticated upstream identity required")
    admission_id = secrets.token_hex(32)
    while admission_id in _ISSUED_ADMISSIONS:
        admission_id = secrets.token_hex(32)
    admission = _unsigned_admission(role=role,
        authorization_fingerprint=authorization_fingerprint,
        authorization_issuance_id=authorization_issuance_id,
        request_fingerprint=request_fingerprint,
        request_issuance_id=request_issuance_id,
        renderer_fingerprint=renderer_fingerprint,
        admission_id=admission_id, process_id=_ISSUER_PID)
    admission = SyntheticReflectionExecutionAdmission(
        admission.scenario_phase_id, admission.scenario_id, admission.observation_role,
        admission.source_sha256, admission.definition_sha256, admission.owner,
        admission.member, admission.declared_type, admission.operation,
        admission.renderer_identity, admission.renderer_fingerprint,
        admission.synthetic_authorization_fingerprint,
        admission.synthetic_authorization_issuance_id,
        admission.reflection_request_fingerprint,
        admission.reflection_request_issuance_id, admission.admission_id,
        admission.issuing_process_id, _signature=_sign(admission))
    _ISSUED_ADMISSIONS[admission.admission_id] = admission
    return validate_synthetic_reflection_execution_admission(admission)


def synthetic_reflection_admission_satisfies_executor(admission,
        authorization, reflection_request) -> bool:
    """Purely authenticate and match all three live objects; never consume."""
    try:
        live_admission = validate_synthetic_reflection_execution_admission(admission)
    except Exception:
        return False
    pair = _validate_upstream_pair(authorization, reflection_request)
    if pair is None:
        return False
    auth, request, renderer_fingerprint = pair
    try:
        return (
            live_admission.observation_role == request.observation_role
            and live_admission.renderer_identity == RENDERER_IDENTITY
            and live_admission.renderer_fingerprint == renderer_fingerprint
            and live_admission.synthetic_authorization_fingerprint == auth.fingerprint
            and live_admission.synthetic_authorization_issuance_id == auth.issuance_id
            and live_admission.reflection_request_fingerprint == request.fingerprint
            and live_admission.reflection_request_issuance_id == request.issuance_id
            and live_admission.consumption_state == ISSUED
        )
    except Exception:
        return False


def _issue_upstream(role: str):
    spec = authorization_owner.executor1r_decrement_3_spec()
    authorization = authorization_owner.issue_synthetic_runtime_authorization(
        spec, source=authorization_owner.get_executor1r_decrement_3_source())
    request = (reflection_owner.executor1r_before_request() if role == BEFORE_ROLE
        else reflection_owner.executor1r_after_request())
    return authorization, request


def verify():
    """Issue and authenticate the two admissions; record no execution effect."""
    before_auth, before_request = _issue_upstream(BEFORE_ROLE)
    after_auth, after_request = _issue_upstream(AFTER_ROLE)
    before = issue_synthetic_reflection_execution_admission(before_auth, before_request)
    after = issue_synthetic_reflection_execution_admission(after_auth, after_request)
    if not synthetic_reflection_admission_satisfies_executor(before, before_auth, before_request):
        _fail("SYNTH_REFLECT_ADMIT_1_BLOCKED_AUTH_COMPATIBILITY", "before binding did not authenticate")
    if not synthetic_reflection_admission_satisfies_executor(after, after_auth, after_request):
        _fail("SYNTH_REFLECT_ADMIT_1_BLOCKED_REFLECT_COMPATIBILITY", "after binding did not authenticate")
    report = {
        "phase_id": PHASE_ID,
        "status": COMPLETE,
        "report_only": True,
        "supported_synthetic_reflection_admission_count": 2,
        "scenario_phase_id": SCENARIO_PHASE_ID,
        "scenario_id": SCENARIO_ID,
        "source_sha256": SOURCE_SHA256,
        "definition_sha256": DEFINITION_SHA256,
        "owner": OWNER,
        "member": MEMBER,
        "declared_type": DECLARED_TYPE,
        "allowed_operation": OPERATION,
        "supported_roles": list(SUPPORTED_ROLES),
        "before_admission": before.as_dict(),
        "after_admission": after.as_dict(),
        "before_admission_identity": before.admission_id,
        "after_admission_identity": after.admission_id,
        "before_request_identity": before.reflection_request_issuance_id,
        "after_request_identity": after.reflection_request_issuance_id,
        "before_authorization_identity": before.synthetic_authorization_issuance_id,
        "after_authorization_identity": after.synthetic_authorization_issuance_id,
        "authenticated_in_issuing_process": True,
        "fresh_synth_auth_1_compatibility": True,
        "fresh_synth_reflect_1_compatibility": True,
        "role_separation_enforced": True,
        "synthetic_reflection_execution_authority": True,
        "runtime_authority": False,
        "real_task_runtime_authority": False,
        "repository_write_authority": False,
        "apply_authority": False,
        "field_write_authority": False,
        "enumeration_authority": False,
        "private_method_authority": False,
        "constructor_reflection_authority": False,
        "arbitrary_class_loading_authority": False,
        "single_execution_use": True,
        "consumption_policy": CONSUMPTION_POLICY,
        "consumption_implemented": False,
        "consumption_state": ISSUED,
        "synthetic_runtime_authorizations_issued": 2,
        "synthetic_runtime_authorizations_consumed": 0,
        "reflection_admissions_consumed": 0,
        "java_compile_count": 0,
        "jvm_execution_count": 0,
        "reflection_execution_count": 0,
        "containers_created": 0,
        "docker_calls": 0,
        "network_calls": 0,
        "shell_calls": 0,
        "child_processes": 0,
        "source_projected": False,
        "measured_observations": None,
        "positive_runtime_receipt": None,
    }
    return (before, after), report
