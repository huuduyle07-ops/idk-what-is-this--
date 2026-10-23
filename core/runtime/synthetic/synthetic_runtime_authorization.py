"""SYNTH.AUTH.1: closed phase-owned synthetic authority, never an executor.

The only supported spec is issued by this owner's no-argument factory. Its
public fields and exported reports cannot establish authority. An authorization
authenticates the supplied exact fixture bytes and invocation in this process;
it grants neither real-task authority nor a reflection capability. Sandbox,
Java and future exact reflection requirements still need separate admission.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from hashlib import sha256
import hmac
import json
import os
import secrets
from weakref import WeakValueDictionary

PHASE_ID = "SYNTH.AUTH.1"
SCHEMA_VERSION = "synthetic_runtime_scenario_spec_v1"
AUTHORIZATION_SCHEMA_VERSION = "synthetic_runtime_authorization_v1"
SCENARIO_PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
SCENARIO_ID = "synthetic.EXECUTOR.1R.decrement_3"
PURPOSE = "phase_owned_synthetic_diagnostic"
SOURCE_KIND = "phase_owned_synthetic_fixture"
SOURCE_SHA256 = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
SANDBOX_PROFILE_ID = "runtime_sandbox_2_v1"
SANDBOX_POLICY_SHA256 = "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75"
JAVA_PROFILE_ID = "RUNTIME.JAVA.1"
JAVA_SCHEMA_VERSION = "runtime_java_1_v1"
ISSUED = "SYNTHETIC_RUNTIME_AUTHORIZATION_ISSUED"
COMPLETE = "SYNTH_AUTH_1_COMPLETE"

# Copied exact phase-owned bytes, not imported through the BANK lineage or any
# runtime owner. No file, class, harness, compiler or JVM is created here.
_SOURCE = (b"final class SyntheticStateBox {\n"
    b"    private int value = 10;\n\n"
    b"    public boolean decrement(int amount) {\n"
    b"        if (amount <= 0 || amount > value) {\n"
    b"            return false;\n"
    b"        }\n"
    b"        value -= amount;\n"
    b"        return true;\n"
    b"    }\n"
    b"}\n")
SOURCE_SIZE_BYTES = 239
_DEFINITION_SHA256 = "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d"
_SECRET = secrets.token_bytes(32)
_ISSUER_PID = os.getpid()
_ISSUED_HANDLES = WeakValueDictionary()


class SyntheticRuntimeAuthorizationError(ValueError):
    def __init__(self, code: str, reason: str = ""):
        self.code = code
        self.reason = reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code: str, reason: str = ""):
    raise SyntheticRuntimeAuthorizationError(code, reason)


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SyntheticInvocationContract:
    owner: str
    public_method: str
    arguments: tuple[int, ...]
    argument_types: tuple[str, ...]
    return_type: str


@dataclass(frozen=True, slots=True)
class SyntheticRequestedFieldMetadata:
    """Requested metadata only; not a REFLECT.1 request or capability."""
    owner: str
    member: str
    declared_type: str
    definition_sha256: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class SyntheticObservationContract:
    roles: tuple[str, ...]
    requested_field_metadata: SyntheticRequestedFieldMetadata
    expected_before: int
    expected_return: bool
    expected_after: int
    future_exact_reflection_required: bool
    reflection_authority: bool


@dataclass(frozen=True, slots=True)
class SyntheticRuntimeScenarioSpec:
    """A closed description; construction alone does not make it supported."""
    schema_version: str
    phase_id: str
    scenario_id: str
    purpose: str
    source_sha256: str
    source_size_bytes: int
    invocation_contract: SyntheticInvocationContract
    observation_contract: SyntheticObservationContract
    sandbox_profile_id: str
    sandbox_policy_sha256: str
    java_profile_id: str
    java_schema_version: str
    allowed_runtime_operations: tuple[str, ...]
    console_required: bool
    network_required: bool
    repository_access_required: bool
    real_task_source: bool
    human_approval_required: bool
    source_kind: str

    @property
    def fingerprint(self) -> str:
        validate_synthetic_runtime_scenario_spec(self)
        return _SPEC_FINGERPRINT

    def as_dict(self) -> dict:
        validate_synthetic_runtime_scenario_spec(self)
        return {**asdict(self), "spec_fingerprint": _SPEC_FINGERPRINT, "report_only": True}


def _fixed_spec() -> SyntheticRuntimeScenarioSpec:
    return SyntheticRuntimeScenarioSpec(
        SCHEMA_VERSION, SCENARIO_PHASE_ID, SCENARIO_ID, PURPOSE,
        SOURCE_SHA256, SOURCE_SIZE_BYTES,
        SyntheticInvocationContract("SyntheticStateBox", "decrement", (3,), ("int",), "boolean"),
        SyntheticObservationContract(
            ("exact_private_state_before", "direct_public_return", "exact_private_state_after"),
            SyntheticRequestedFieldMetadata("SyntheticStateBox", "value", "int",
                _DEFINITION_SHA256, SOURCE_SHA256),
            10, True, 7, True, False),
        SANDBOX_PROFILE_ID, SANDBOX_POLICY_SHA256, JAVA_PROFILE_ID, JAVA_SCHEMA_VERSION,
        ("direct_public_invocation",), False, False, False, False, False, SOURCE_KIND)


_SUPPORTED_SPEC = _fixed_spec()
_SPEC_JSON = _json(asdict(_SUPPORTED_SPEC))
_SPEC_FINGERPRINT = sha256(_SPEC_JSON.encode("utf-8")).hexdigest()


def _exact_shape(value, template) -> bool:
    """Reject mutable/foreign nested values before serializing or comparing."""
    if type(value) is not type(template):
        return False
    if type(template) in {SyntheticRuntimeScenarioSpec, SyntheticInvocationContract,
            SyntheticObservationContract, SyntheticRequestedFieldMetadata}:
        return all(_exact_shape(getattr(value, f.name), getattr(template, f.name))
            for f in fields(template))
    if type(template) is tuple:
        return len(value) == len(template) and all(
            _exact_shape(v, t) for v, t in zip(value, template))
    return value == template


def validate_synthetic_runtime_scenario_spec(spec: SyntheticRuntimeScenarioSpec):
    # Identity distinguishes the owner's supported constant from public typed
    # copies, matching strings, dataclasses.replace(), and reconstructed JSON.
    if (spec is not _SUPPORTED_SPEC or not _exact_shape(spec, _fixed_spec())
            or _json(asdict(spec)) != _SPEC_JSON):
        _fail("synthetic_scenario_not_supported", "exact owner-issued V1 spec required")
    return spec


def executor1r_decrement_3_spec() -> SyntheticRuntimeScenarioSpec:
    return validate_synthetic_runtime_scenario_spec(_SUPPORTED_SPEC)


def get_executor1r_decrement_3_source() -> bytes:
    _validate_source(_SOURCE)
    return _SOURCE


def _validate_source(source: bytes):
    if (type(source) is not bytes or len(source) != SOURCE_SIZE_BYTES
            or sha256(source).hexdigest() != SOURCE_SHA256 or source != _SOURCE):
        _fail("synthetic_source_mismatch", "exact phase-owned bytes, size and SHA-256 required")


class _LocalHandle:
    __slots__ = ("__weakref__",)


@dataclass(frozen=True, slots=True)
class SyntheticRuntimeAuthorization(_LocalHandle):
    """Authenticated local synthetic scope; exported data is never authority."""
    issuance_id: str
    issuer_process_id: int
    spec_fingerprint: str
    source_sha256: str
    source_size_bytes: int
    scenario_phase_id: str
    scenario_id: str
    sandbox_profile_id: str
    sandbox_policy_sha256: str
    java_profile_id: str
    java_schema_version: str
    source_kind: str
    allowed_runtime_operations: tuple[str, ...]
    _signature: str = field(default="", repr=False, compare=False)
    issuer_phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=AUTHORIZATION_SCHEMA_VERSION, init=False)
    status: str = field(default=ISSUED, init=False)
    purpose: str = field(default=PURPOSE, init=False)
    synthetic_runtime_authority: bool = field(default=True, init=False)
    future_exact_reflection_required: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    real_task_source: bool = field(default=False, init=False)
    human_approval_required: bool = field(default=False, init=False)
    real_human_approval: bool = field(default=False, init=False)
    real_session_consumed: bool = field(default=False, init=False)
    operational_real_task_source: bool = field(default=False, init=False)
    reflection_authority: bool = field(default=False, init=False)
    reflection_capability_available: bool = field(default=False, init=False)
    sandbox_capability_available: bool = field(default=False, init=False)
    java_capability_available: bool = field(default=False, init=False)
    execution_ready: bool = field(default=False, init=False)
    execution_completed: bool = field(default=False, init=False)
    repository_access_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    console_authority: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    compile_count: int = field(default=0, init=False)
    jvm_execution_count: int = field(default=0, init=False)
    reflection_execution_count: int = field(default=0, init=False)
    real_runtime_authorizations_consumed: int = field(default=0, init=False)
    synthetic_runtime_authorizations_consumed: int = field(default=0, init=False)

    @property
    def fingerprint(self) -> str:
        validate_synthetic_runtime_authorization(self, spec=_SUPPORTED_SPEC, source=_SOURCE)
        return _hash(_authorization_payload(self))

    def as_dict(self) -> dict:
        return {**_authorization_payload_validated(self),
            "authorization_fingerprint": self.fingerprint, "report_only": True}


def _authorization_payload(authorization) -> dict:
    return {f.name: getattr(authorization, f.name) for f in fields(SyntheticRuntimeAuthorization)
        if f.name != "_signature"}


def _authorization_payload_validated(authorization) -> dict:
    validate_synthetic_runtime_authorization(authorization, spec=_SUPPORTED_SPEC, source=_SOURCE)
    return _authorization_payload(authorization)


def _unsigned_authorization(spec, issuance_id, issuer_process_id):
    return SyntheticRuntimeAuthorization(issuance_id, issuer_process_id,
        _SPEC_FINGERPRINT, spec.source_sha256, spec.source_size_bytes, spec.phase_id,
        spec.scenario_id, spec.sandbox_profile_id, spec.sandbox_policy_sha256,
        spec.java_profile_id, spec.java_schema_version, spec.source_kind,
        spec.allowed_runtime_operations)


def _sign(authorization) -> str:
    return hmac.new(_SECRET, _json(_authorization_payload(authorization)).encode("utf-8"),
        "sha256").hexdigest()


def _local_process():
    if os.getpid() != _ISSUER_PID:
        _fail("synthetic_authorization_unauthenticated", "issuing process required")


def issue_synthetic_runtime_authorization(spec: SyntheticRuntimeScenarioSpec, *, source: bytes):
    _local_process()
    validate_synthetic_runtime_scenario_spec(spec)
    _validate_source(source)
    authorization = _unsigned_authorization(spec, secrets.token_hex(32), _ISSUER_PID)
    authorization = replace(authorization, _signature=_sign(authorization))
    _ISSUED_HANDLES[authorization.issuance_id] = authorization
    return validate_synthetic_runtime_authorization(authorization, spec=spec, source=source)


def validate_synthetic_runtime_authorization(authorization: SyntheticRuntimeAuthorization,
        *, spec: SyntheticRuntimeScenarioSpec, source: bytes):
    _local_process()
    validate_synthetic_runtime_scenario_spec(spec)
    _validate_source(source)
    if type(authorization) is not SyntheticRuntimeAuthorization:
        _fail("synthetic_authorization_unauthenticated", "owner-issued typed local handle required")
    if (type(authorization.issuance_id) is not str or len(authorization.issuance_id) != 64
            or any(c not in "0123456789abcdef" for c in authorization.issuance_id)
            or _ISSUED_HANDLES.get(authorization.issuance_id) is not authorization
            or type(authorization.issuer_process_id) is not int
            or authorization.issuer_process_id != _ISSUER_PID):
        _fail("synthetic_authorization_unauthenticated", "live issuance provenance required")
    expected = _authorization_payload(_unsigned_authorization(spec,
        authorization.issuance_id, _ISSUER_PID))
    payload = _authorization_payload(authorization)
    if any(not _exact_shape(payload[k], v) for k, v in expected.items()):
        _fail("synthetic_authorization_scope_mismatch", "exact immutable synthetic scope required")
    if (type(authorization._signature) is not str or len(authorization._signature) != 64
            or any(c not in "0123456789abcdef" for c in authorization._signature)
            or not hmac.compare_digest(authorization._signature, _sign(authorization))):
        _fail("synthetic_authorization_unauthenticated", "process-local issuer authentication required")
    return authorization


def verify():
    """Prove contract issuance only; expected facts are never measurements."""
    spec = executor1r_decrement_3_spec()
    authorization = issue_synthetic_runtime_authorization(spec,
        source=get_executor1r_decrement_3_source())
    report = {"phase_id": PHASE_ID, "status": COMPLETE,
        "spec": spec.as_dict(), "synthetic_authorization": authorization.as_dict(),
        "authenticated_in_issuing_process": True, "exported_json_is_report_only": True,
        "supported_scenario_count": 1, "synthetic_authorizations_issued": 1,
        "requested_semantic_facts": {"before": 10, "return": True, "after": 7},
        "measured_observations": None, "positive_runtime_receipt": None,
        "future_exact_reflection_required": True, "reflection_authority": False,
        "execution_ready": False, "execution_completed": False,
        "real_runtime_authority_available": False, "real_human_approval": False,
        "real_session_consumed": False, "source_projected": False,
        "harness_rendered": False, "compile_count": 0, "jvm_execution_count": 0,
        "reflection_execution_count": 0, "console_count": 0,
        "bank_execution_count": 0, "real_behavioral_execution_count": 0,
        "synthetic_behavioral_execution_count": 0, "real_runtime_authorizations_consumed": 0,
        "synthetic_runtime_authorizations_consumed": 0,
        "repository_writes": 0, "apply_actions": 0, "model_calls": 0, "author_calls": 0,
        "phase_containers_created": 0, "remaining_phase_containers": None,
        "cleanup_outcome": "not_required_no_runtime_resources_created"}
    return authorization, report
