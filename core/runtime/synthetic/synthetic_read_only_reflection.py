"""SYNTH.REFLECT.1: exact synthetic observation requests, with no execution.

Only live requests from this owner's two factories validate. Rendering is pure
text generation; neither a request nor compatible SYNTH.AUTH.1 grants runtime
admission. Observation data is a future result shape, never a measured receipt.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from hashlib import sha256
import hmac
import json
import os
import secrets
from weakref import WeakValueDictionary

from core.runtime.synthetic import synthetic_runtime_authorization as authorization_owner

PHASE_ID = "SYNTH.REFLECT.1"
SCHEMA_VERSION = "synthetic_reflection_request_v1"
SCENARIO_PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
SCENARIO_ID = "synthetic.EXECUTOR.1R.decrement_3"
SOURCE_SHA256 = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
DEFINITION_SHA256 = "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d"
SOURCE_KIND = "phase_owned_synthetic_fixture"
BEFORE_ROLE = "exact_private_state_before"
AFTER_ROLE = "exact_private_state_after"
COMPLETE = "SYNTH_REFLECT_1_COMPLETE"

_SECRET = secrets.token_bytes(32)
_ISSUER_PID = os.getpid()
_ISSUED_REQUESTS = WeakValueDictionary()


class SyntheticReflectionError(ValueError):
    def __init__(self, code: str, reason: str = ""):
        self.code = code
        self.reason = reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code: str, reason: str = ""):
    raise SyntheticReflectionError(code, reason)


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def validate_synthetic_definition(source: bytes):
    """Verify the one fixed declaration in the entire pinned fixture.

    This deliberately has no Java discovery/parser API. Exact source equality
    fixes the lexical owner and declaration position before its slice is hashed,
    using the same raw-declaration SHA-256 convention as historical REFLECT.1.
    """
    expected = authorization_owner.get_executor1r_decrement_3_source()
    if (type(source) is not bytes or len(source) != 239 or source != expected
            or sha256(source).hexdigest() != SOURCE_SHA256):
        _fail("synthetic_definition_mismatch", "exact 239-byte phase-owned source required")
    declaration = source[36:59]
    if (source[:36] != b"final class SyntheticStateBox {\n    "
            or declaration != b"private int value = 10;"
            or sha256(declaration).hexdigest() != DEFINITION_SHA256):
        _fail("synthetic_definition_mismatch", "exact private primitive instance declaration required")


class _LocalRequest:
    __slots__ = ("__weakref__",)


@dataclass(frozen=True, slots=True)
class SyntheticReflectionRequest(_LocalRequest):
    """Public construction is data only; validation requires live provenance."""
    schema_version: str
    phase_id: str
    scenario_id: str
    source_sha256: str
    definition_sha256: str
    owner: str
    member: str
    declared_type: str
    operation: str
    observation_role: str
    source_kind: str
    issuance_id: str
    issuer_process_id: int
    _signature: str = field(default="", repr=False, compare=False)
    reflection_request_valid: bool = field(default=True, init=False)
    reflection_execution_authority: bool = field(default=False, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    field_write_authority: bool = field(default=False, init=False)
    enumeration_authority: bool = field(default=False, init=False)
    private_method_authority: bool = field(default=False, init=False)
    execution_ready: bool = field(default=False, init=False)

    @property
    def fingerprint(self) -> str:
        validate_synthetic_reflection_request(self)
        return _pinned_fingerprint(self.observation_role)

    def as_dict(self) -> dict:
        validate_synthetic_reflection_request(self)
        return {**_payload(self), "request_fingerprint": self.fingerprint, "report_only": True}


def _fixed_request(role, issuance_id, process_id):
    return SyntheticReflectionRequest(SCHEMA_VERSION, SCENARIO_PHASE_ID, SCENARIO_ID,
        SOURCE_SHA256, DEFINITION_SHA256, "SyntheticStateBox", "value", "int",
        "read_exact_bound_field", role, SOURCE_KIND, issuance_id, process_id)


def _payload(request) -> dict:
    return {f.name: getattr(request, f.name) for f in fields(SyntheticReflectionRequest)
        if f.name != "_signature"}


def _contract_payload(request) -> dict:
    return {k: v for k, v in _payload(request).items()
        if k not in {"issuance_id", "issuer_process_id"}}


def _pinned_fingerprint(role):
    # Literal pins are independent of callers, issuance, and mutable instances.
    if role == BEFORE_ROLE:
        return "dbffd8211482a3c8771b0a4cb06488962757991fa812b49855113192588a3aa1"
    if role == AFTER_ROLE:
        return "d8f404b4214f5f90b15b6b50e5bb9395f7cf472baa654d0e80c439118f763f5e"
    _fail("synthetic_reflection_scope_mismatch", "one of the two exact private roles required")


def _exact_immutable(value, template) -> bool:
    if type(value) is not type(template):
        return False
    if type(template) is tuple:
        return len(value) == len(template) and all(
            _exact_immutable(v, t) for v, t in zip(value, template))
    # V1 has scalar fields only. Foreign containers/proxies cannot be serialized
    # into a projection or compare as equal to an immutable scalar.
    return type(value) in {str, int, bool} and value == template


def _local_process():
    if os.getpid() != _ISSUER_PID:
        _fail("synthetic_reflection_unauthenticated", "issuing process required")


def _hex_id(value) -> bool:
    return (type(value) is str and len(value) == 64
        and all(c in "0123456789abcdef" for c in value))


def _sign(request):
    return hmac.new(_SECRET, _json(_payload(request)).encode("utf-8"), "sha256").hexdigest()


def validate_synthetic_reflection_request(request: SyntheticReflectionRequest):
    _local_process()
    if type(request) is not SyntheticReflectionRequest:
        _fail("synthetic_reflection_unauthenticated", "exact owner-issued typed request required")
    if any(not hasattr(request, f.name) for f in fields(SyntheticReflectionRequest)):
        _fail("synthetic_reflection_unauthenticated", "complete issued request required")
    if (not _hex_id(request.issuance_id)
            or _ISSUED_REQUESTS.get(request.issuance_id) is not request
            or type(request.issuer_process_id) is not int
            or request.issuer_process_id != _ISSUER_PID):
        _fail("synthetic_reflection_unauthenticated", "live request issuance provenance required")
    if (type(request.observation_role) is not str
            or request.observation_role not in (BEFORE_ROLE, AFTER_ROLE)):
        _fail("synthetic_reflection_scope_mismatch", "exact private observation role required")
    expected = _payload(_fixed_request(request.observation_role, request.issuance_id, _ISSUER_PID))
    actual = _payload(request)
    if (any(not _exact_immutable(actual[k], v) for k, v in expected.items())
            or _json(actual) != _json(expected)
            or _hash(_contract_payload(request)) != _pinned_fingerprint(request.observation_role)):
        _fail("synthetic_reflection_scope_mismatch", "exact immutable complete pinned projection required")
    if not _hex_id(request._signature) or not hmac.compare_digest(request._signature, _sign(request)):
        _fail("synthetic_reflection_unauthenticated", "independent process-local authentication required")
    validate_synthetic_definition(authorization_owner.get_executor1r_decrement_3_source())
    return request


def _issue(role):
    _local_process()
    validate_synthetic_definition(authorization_owner.get_executor1r_decrement_3_source())
    request = _fixed_request(role, secrets.token_hex(32), _ISSUER_PID)
    request = replace(request, _signature=_sign(request))
    _ISSUED_REQUESTS[request.issuance_id] = request
    return validate_synthetic_reflection_request(request)


def executor1r_before_request() -> SyntheticReflectionRequest:
    return _issue(BEFORE_ROLE)


def executor1r_after_request() -> SyntheticReflectionRequest:
    return _issue(AFTER_ROLE)


def synthetic_reflection_satisfies_authorization(reflection_request, synthetic_authorization) -> bool:
    """Pure compatibility only; never consumes or changes either local handle."""
    if (type(synthetic_authorization) is not authorization_owner.SyntheticRuntimeAuthorization
            or any(not hasattr(synthetic_authorization, f.name)
                for f in fields(authorization_owner.SyntheticRuntimeAuthorization))):
        return False
    try:
        request = validate_synthetic_reflection_request(reflection_request)
        spec = authorization_owner.executor1r_decrement_3_spec()
        auth = authorization_owner.validate_synthetic_runtime_authorization(
            synthetic_authorization, spec=spec,
            source=authorization_owner.get_executor1r_decrement_3_source())
    except (SyntheticReflectionError, authorization_owner.SyntheticRuntimeAuthorizationError):
        return False
    observation = spec.observation_contract
    metadata = observation.requested_field_metadata
    return (
        request.scenario_id == auth.scenario_id == spec.scenario_id == SCENARIO_ID
        and request.phase_id == auth.scenario_phase_id == spec.phase_id == SCENARIO_PHASE_ID
        and request.source_sha256 == auth.source_sha256 == metadata.source_sha256 == SOURCE_SHA256
        and (request.owner, request.member, request.declared_type, request.definition_sha256)
            == (metadata.owner, metadata.member, metadata.declared_type, metadata.definition_sha256)
            == ("SyntheticStateBox", "value", "int", DEFINITION_SHA256)
        and request.source_kind == auth.source_kind == spec.source_kind == SOURCE_KIND
        and observation.roles == (BEFORE_ROLE, "direct_public_return", AFTER_ROLE)
        and request.observation_role in (BEFORE_ROLE, AFTER_ROLE)
        and observation.future_exact_reflection_required is True
        and auth.future_exact_reflection_required is True
        and observation.reflection_authority is False
        and auth.reflection_authority is False
        and auth.execution_ready is False
    )


# Full helper literals keep every Java reflection argument and primitive reader
# outside caller control. These strings are not compiled, loaded, or executed.
_BEFORE_HELPER = '''private static int observeSyntheticValueBefore(SyntheticStateBox instance)
        throws ReflectiveOperationException {
    Class<?> owner = SyntheticStateBox.class;
    java.lang.reflect.Field field = owner.getDeclaredField("value");
    field.setAccessible(true);
    int observed = field.getInt(instance);
    return observed;
}
'''
_AFTER_HELPER = '''private static int observeSyntheticValueAfter(SyntheticStateBox instance)
        throws ReflectiveOperationException {
    Class<?> owner = SyntheticStateBox.class;
    java.lang.reflect.Field field = owner.getDeclaredField("value");
    field.setAccessible(true);
    int observed = field.getInt(instance);
    return observed;
}
'''


def render_synthetic_read_only_reflection(request: SyntheticReflectionRequest) -> str:
    validate_synthetic_reflection_request(request)
    return _BEFORE_HELPER if request.observation_role == BEFORE_ROLE else _AFTER_HELPER


@dataclass(frozen=True, slots=True)
class SyntheticPrivateFieldObservation:
    """Data shape for a future measurement; construction proves no execution.

    No factory here reads a value. A later executor must authenticate where its
    measurement came from; this shape does not grant authority or prove origin.
    """
    scenario_id: str
    role: str
    owner: str
    member: str
    declared_type: str
    measured_value: int
    source_sha256: str
    definition_sha256: str

    def __post_init__(self):
        validate_synthetic_private_field_observation(self)


def validate_synthetic_private_field_observation(observation: SyntheticPrivateFieldObservation):
    if type(observation) is not SyntheticPrivateFieldObservation:
        _fail("synthetic_observation_invalid", "exact typed data shape required")
    if any(not hasattr(observation, f.name) for f in fields(SyntheticPrivateFieldObservation)):
        _fail("synthetic_observation_invalid", "complete typed data shape required")
    expected = {"scenario_id": SCENARIO_ID, "owner": "SyntheticStateBox", "member": "value",
        "declared_type": "int", "source_sha256": SOURCE_SHA256, "definition_sha256": DEFINITION_SHA256}
    if (any(not _exact_immutable(getattr(observation, k), v) for k, v in expected.items())
            or type(observation.role) is not str or observation.role not in (BEFORE_ROLE, AFTER_ROLE)
            or type(observation.measured_value) is not int
            or not -(2 ** 31) <= observation.measured_value < 2 ** 31):
        _fail("synthetic_observation_invalid", "exact target, private role and primitive int value required")
    return observation


def verify():
    """Prove request/auth compatibility and pure rendering, never measure Java."""
    before, after = executor1r_before_request(), executor1r_after_request()
    spec = authorization_owner.executor1r_decrement_3_spec()
    auth = authorization_owner.issue_synthetic_runtime_authorization(spec,
        source=authorization_owner.get_executor1r_decrement_3_source())
    if not all(synthetic_reflection_satisfies_authorization(r, auth) for r in (before, after)):
        _fail("SYNTH_REFLECT_1_BLOCKED_AUTH_COMPATIBILITY")
    if any(synthetic_reflection_satisfies_authorization(r, auth.as_dict()) for r in (before, after)):
        _fail("SYNTH_REFLECT_1_BLOCKED_AUTH_COMPATIBILITY", "report cannot authorize")
    rendered = tuple(render_synthetic_read_only_reflection(r) for r in (before, after))
    report = {
        "phase_id": PHASE_ID, "status": COMPLETE, "report_only": True,
        "supported_synthetic_reflection_target_count": 1,
        "scenario_phase_id": SCENARIO_PHASE_ID, "scenario_id": SCENARIO_ID,
        "source_sha256": SOURCE_SHA256, "source_size_bytes": 239,
        "definition_sha256": DEFINITION_SHA256,
        "owner": "SyntheticStateBox", "member": "value", "declared_type": "int",
        "allowed_operation": "read_exact_bound_field", "supported_roles": [BEFORE_ROLE, AFTER_ROLE],
        "requests": [before.as_dict(), after.as_dict()],
        "renderer_boundary": "fixed SyntheticStateBox.class / value / getInt; role-specific helper literals",
        "rendered_helpers": list(rendered),
        "renderer_sha256": [sha256(s.encode("utf-8")).hexdigest() for s in rendered],
        "reflection_request_valid": True, "reflection_execution_authority": False,
        "field_write_authority": False, "enumeration_authority": False,
        "private_method_authority": False, "fresh_synth_auth_1_compatible": True,
        "copied_exported_authorization_rejected": True,
        "exported_json_can_recreate_authority": False,
        "runtime_authority": False, "real_task_runtime_authority": False,
        "repository_write_authority": False, "apply_authority": False,
        "execution_ready": False, "execution_completed": False,
        "compile_count": 0, "jvm_execution_count": 0, "reflection_execution_count": 0,
        "containers_created": 0, "authorization_consumed": 0,
        "synthetic_runtime_authorizations_consumed": 0, "real_runtime_authorizations_consumed": 0,
        "source_projected": False, "repository_writes": 0,
        "measured_observations": None, "positive_runtime_receipt": None,
    }
    return (before, after), report
