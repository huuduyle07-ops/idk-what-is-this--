"""SYNTH.AUTH.LIFECYCLE.PINNED.1: additive, process-local pinned leases.

Only the unchanged public pinned authorization validator authenticates upstream.
This owner performs no behavior. Consumer/source/compile contracts remain
unresolved, so consumption always fails closed. Reports never restore a lease.
Permanent records retain the original authorization and a weak lease identity;
one immutable store replacement publishes issuance or a terminal transition.
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

from core.runtime.synthetic import synthetic_runtime_authorization_pinned as authorization_owner
from core.runtime_java_pinned_requirement import REQUIREMENT

OWNER_ID = "core.synthetic_runtime_authorization_pinned_lifecycle"
PHASE_ID = "SYNTH.AUTH.LIFECYCLE.PINNED.1"
SCHEMA_VERSION = "synthetic_runtime_execution_lease_pinned_1_v1"
COMPLETE = "SYNTH_AUTH_LIFECYCLE_PINNED_1A_COMPLETE"
ISSUED, CONSUMED, INVALIDATED = "ISSUED", "CONSUMED", "INVALIDATED"
SCENARIO_PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
SOURCE_KIND = "phase_owned_synthetic_fixture"
ACTIVATION_POLICY_ID = "SYNTH.AUTH.LIFECYCLE.PINNED.1:exact-decrement-3-activation:v1"
ERROR_CODES = (
    "PINNED_AUTH_UNAUTHENTICATED", "PINNED_AUTH_SCOPE_MISMATCH",
    "PINNED_PROVIDER_PROVENANCE_MISMATCH", "DUPLICATE_LEASE_ISSUANCE",
    "LEASE_UNAUTHENTICATED", "LEASE_WRONG_PROCESS", "LEASE_NOT_ISSUED",
    "LEASE_ALREADY_CONSUMED", "LEASE_INVALIDATED",
    "ACTIVATION_PRECONDITION_UNSATISFIED", "PROOF_UNRESOLVED",
)
_DOMAIN = b"CATTUS:SYNTH.AUTH.LIFECYCLE.PINNED.1:exact-execution-lease:v1"
_SECRET = secrets.token_bytes(32)
_ISSUER_PID = os.getpid()
_LOCK = Lock()
_FALSE_AUTHORITY = (
    "runtime_authority", "real_task_runtime_authority", "repository_write_authority",
    "apply_authority", "network_authority", "host_mount_authority", "shell_authority",
    "arbitrary_java_authority", "arbitrary_class_authority", "arbitrary_method_authority",
    "arbitrary_source_authority", "repository_java_authority", "arbitrary_command_authority",
    "executor_authority", "BANK_authority", "reflection_execution_authority",
    "compilation_authority",
)
_PROVIDER_FIELDS = (
    "phase_id", "schema_version", "owner_identity", "proof_context_identity", "receipt_id",
    "fingerprint", "evidence_digest", "requirement_profile", "requirement_schema",
    "target_image_identity", "runtime_sandbox_profile", "runtime_sandbox_policy_sha256",
    "controller_identity_evidence_json", "cleanup_evidence_json", "cleanup_evidence_digest",
)


class PinnedSyntheticRuntimeExecutionLeaseError(ValueError):
    def __init__(self, code, reason="", *, upstream_code=None, upstream_reason=None):
        self.code, self.reason = code, reason or code
        self.category = "LEASE_NOT_ISSUED" if code in (
            "LEASE_ALREADY_CONSUMED", "LEASE_INVALIDATED") else code
        self.upstream_code, self.upstream_reason = upstream_code, upstream_reason
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise PinnedSyntheticRuntimeExecutionLeaseError(code, reason)


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
            "activation-policy", "lease-evidence", "lease-fingerprint", "lease-record-hmac"):
        raise ValueError("unknown lifecycle authentication role")
    return _DOMAIN + b"\x00" + role.encode("utf-8") + b"\x00" + _canonical(value).encode("utf-8")


def _digest(value, role):
    return sha256(_framed(value, role)).hexdigest()


def _activation_policy():
    # Exact frozen contract projection; no consumer token or compilation placement.
    return {
        "identity": ACTIVATION_POLICY_ID,
        "identity_and_canonical_policy_digest_bound_in_lease": True,
        "old_consumption_policy_unchanged": True,
        "valid_original_pinned_authorization_required": True,
        "retained_authenticated_provider_graph_required": True,
        "requirement_profile": "RUNTIME.JAVA.PINNED.1",
        "requirement_schema": "runtime_java_pinned_1_v1",
        "runtime_sandbox_profile": "runtime_sandbox_2_v1",
        "runtime_sandbox_policy_sha256": "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75",
        "immutable_target_identity_source": "validated_original_authorization.provider.target_image_identity == core.runtime_java_pinned_requirement.REQUIREMENT.image_identity",
        "provider_checks_via_mandatory_upstream_public_validator": True,
        "additional_runtime_readiness_evidence_owner": None,
        "invented_runtime_readiness_token_allowed": False,
        "lease_local_preconditions": ["original authenticated lease", "exact original pinned authorization", "ISSUED", "authenticated scenario and provider projections", "exact activation policy identity and digest"],
        "behavioral_activation_prerequisites": ["all consumer capability/authentication gates resolved by separately reviewed pinned consumer contract", "exact source/harness readiness authenticated by that consumer", "source projection and scenario compilation classification resolved before any authorized preparation", "repeat lease-local preconditions atomically at consumption"],
        "lease_local_ready_implies_behavioral_ready": False,
        "behavioral_readiness_established_by_this_phase": False,
        "unresolved_dependency_error": "PROOF_UNRESOLVED",
    }


ACTIVATION_POLICY_DIGEST = _digest(_activation_policy(), "activation-policy")


def _hex_id(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _local_lock(value=None):
    # A foreign process must never wait on an inherited owner lock.
    pid = os.getpid()
    if type(pid) is not int or pid != _ISSUER_PID:
        _fail("LEASE_WRONG_PROCESS", "issuing owner process required")
    if type(value) in (PinnedSyntheticRuntimeExecutionLease,
            authorization_owner.PinnedSyntheticRuntimeAuthorization):
        issuing_pid = getattr(value, "issuing_pid", None)
        if type(issuing_pid) is int and issuing_pid != _ISSUER_PID:
            _fail("LEASE_WRONG_PROCESS", "original issuing PID required")
    return _LOCK


def _upstream_failure(error):
    code = getattr(error, "code", getattr(error, "status", None))
    reason = getattr(error, "reason", str(error))
    category = "PROOF_UNRESOLVED"
    if isinstance(error, authorization_owner.PinnedSyntheticAuthorizationError):
        if code == "pinned_synthetic_authorization_unauthenticated":
            category = "PINNED_AUTH_UNAUTHENTICATED"
        elif code == "pinned_synthetic_authorization_scope_mismatch":
            category = "PINNED_AUTH_SCOPE_MISMATCH"
        elif code in ("pinned_provider_original_outcome_required", "pinned_provider_original_binding_required",
                "pinned_provider_incomplete", "pinned_provider_proof_only_required",
                "pinned_provider_exact_requirement_required", "pinned_synthetic_provider_graph_mismatch"):
            category = "PINNED_PROVIDER_PROVENANCE_MISMATCH"
    elif isinstance(error, authorization_owner.provider_owner.PinnedProviderBlocked):
        if code in ("PINNED_BACKEND_BINDING_MISMATCH", "PINNED_RUNTIME_EVIDENCE_MISMATCH",
                "PINNED_CONTROLLER_MISMATCH", "PINNED_CLEANUP_FAILURE"):
            category = "PINNED_PROVIDER_PROVENANCE_MISMATCH"
    raise PinnedSyntheticRuntimeExecutionLeaseError(category, str(reason),
        upstream_code=code, upstream_reason=reason) from error


def _scenario_projection(scenario):
    if type(scenario) is not authorization_owner.PinnedSyntheticScenarioIdentity:
        _fail("PINNED_AUTH_SCOPE_MISMATCH", "exact authenticated scenario type required")
    expected = {
        "scenario_id": "synthetic.EXECUTOR.1R.decrement_3",
        "source_sha256": "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302",
        "source_size_bytes": 239,
        "definition_sha256": "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d",
        "class_name": "SyntheticStateBox", "method_name": "decrement",
        "method_signature": "boolean SyntheticStateBox.decrement(int)",
        "arguments": (3,), "argument_types": ("int",), "return_type": "boolean",
        "field_owner": "SyntheticStateBox", "field_name": "value", "field_type": "int",
        "expected_before": 10, "expected_return": True, "expected_after": 7,
    }
    projection = {}
    for name, value in expected.items():
        actual = getattr(scenario, name, None)
        if type(actual) is not type(value) or actual != value:
            _fail("PINNED_AUTH_SCOPE_MISMATCH", "exact scenario field required: " + name)
        if type(value) is tuple and any(type(a) is not type(b) for a, b in zip(actual, value)):
            _fail("PINNED_AUTH_SCOPE_MISMATCH", "exact scenario element types required: " + name)
        projection[name] = list(actual) if type(actual) is tuple else actual
    return projection


def _provider_projection(provider):
    if type(provider) is not authorization_owner.PinnedSyntheticProviderIdentity:
        _fail("PINNED_PROVIDER_PROVENANCE_MISMATCH", "exact authenticated provider projection required")
    projection = {name: getattr(provider, name, None) for name in _PROVIDER_FIELDS}
    if any(type(value) is not str or not value for value in projection.values()):
        _fail("PINNED_PROVIDER_PROVENANCE_MISMATCH", "exact provider string fields required")
    expected = {"phase_id": "RUNTIME.JAVA.PINNED.1C",
        "schema_version": "runtime_java_pinned_provider_1c_v1",
        "owner_identity": "core.runtime_java_pinned_provider",
        "requirement_profile": "RUNTIME.JAVA.PINNED.1",
        "requirement_schema": "runtime_java_pinned_1_v1",
        "target_image_identity": REQUIREMENT.image_identity,
        "runtime_sandbox_profile": "runtime_sandbox_2_v1",
        "runtime_sandbox_policy_sha256": "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75"}
    if any(projection[name] != value for name, value in expected.items()):
        _fail("PINNED_PROVIDER_PROVENANCE_MISMATCH", "exact pinned provider/policy required")
    return projection


def _authenticate_authorization(authorization):
    if type(authorization) is not authorization_owner.PinnedSyntheticRuntimeAuthorization:
        _fail("PINNED_AUTH_UNAUTHENTICATED", "exact original pinned authorization required")
    try:
        original = authorization_owner.validate_pinned_synthetic_runtime_authorization(authorization)
    except Exception as error:
        _upstream_failure(error)
    if original is not authorization:
        _fail("PINNED_AUTH_UNAUTHENTICATED", "public validator must return the same original object")
    expected = {"owner_identity": "core.synthetic_runtime_authorization_pinned",
        "phase_id": "SYNTH.AUTH.PINNED.1", "schema_version": "synthetic_runtime_authorization_pinned_1_v1"}
    if any(type(getattr(original, name, None)) is not str or getattr(original, name) != value
            for name, value in expected.items()):
        _fail("PINNED_AUTH_SCOPE_MISMATCH", "exact pinned authorization epoch required")
    if (type(original.issuing_pid) is not int or original.issuing_pid != _ISSUER_PID
            or not _hex_id(original.authorization_id) or not _hex_id(original.proof_context_id)):
        _fail("PINNED_AUTH_UNAUTHENTICATED", "exact authenticated process and identifiers required")
    _scenario_projection(original.scenario)
    _provider_projection(original.provider)
    return original


def _authorization_fingerprint(authorization):
    try:
        fingerprint = authorization.fingerprint
    except Exception as error:
        _upstream_failure(error)
    if not _hex_id(fingerprint):
        _fail("PINNED_AUTH_UNAUTHENTICATED", "authenticated fingerprint required")
    return fingerprint


def _one_shot_key(authorization):
    return (authorization.owner_identity, authorization.phase_id, authorization.schema_version,
        authorization.issuing_pid, authorization.authorization_id)


class _LocalLease:
    __slots__ = ("__weakref__",)


@dataclass(frozen=True, slots=True)
class PinnedSyntheticRuntimeExecutionLease(_LocalLease):
    authorization_id: str
    authorization_fingerprint: str
    authorization_proof_context_id: str
    issuing_pid: int
    scenario: authorization_owner.PinnedSyntheticScenarioIdentity
    provider: authorization_owner.PinnedSyntheticProviderIdentity
    activation_policy_identity: str
    activation_policy_digest: str
    lease_id: str
    evidence_digest: str
    stable_fingerprint: str
    owner_identity: str = field(default=OWNER_ID, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    scenario_phase_id: str = field(default=SCENARIO_PHASE_ID, init=False)
    source_kind: str = field(default=SOURCE_KIND, init=False)
    initial_state: str = field(default=ISSUED, init=False)
    lease_issued: bool = field(default=True, init=False)
    one_shot_exact_synthetic_activation_capability: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)
    shell_authority: bool = field(default=False, init=False)
    arbitrary_java_authority: bool = field(default=False, init=False)
    arbitrary_class_authority: bool = field(default=False, init=False)
    arbitrary_method_authority: bool = field(default=False, init=False)
    arbitrary_source_authority: bool = field(default=False, init=False)
    repository_java_authority: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    executor_authority: bool = field(default=False, init=False)
    BANK_authority: bool = field(default=False, init=False)
    reflection_execution_authority: bool = field(default=False, init=False)
    compilation_authority: bool = field(default=False, init=False)

    @property
    def fingerprint(self):
        with _local_lock(self):
            _authenticated_record_locked(self)
            return self.stable_fingerprint

    @property
    def lifecycle_state(self):
        return pinned_synthetic_runtime_execution_lease_state(self)

    @property
    def runtime_activation_consumed(self):
        return pinned_synthetic_runtime_execution_lease_state(self) == CONSUMED

    def as_dict(self):
        with _local_lock(self):
            record = _authenticated_record_locked(self)
            return {**_projection(self), "current_state": record.lifecycle_state,
                "runtime_activation_consumed": record.lifecycle_state == CONSUMED,
                "report_only": True}


@dataclass(frozen=True, slots=True)
class PinnedSyntheticRuntimeExecutionLeaseReadiness:
    lease_local_preconditions_satisfied: bool
    behavioral_activation_ready: bool
    current_state: str
    reason: str
    report_only: bool = field(default=True, init=False)


@dataclass(frozen=True, slots=True)
class _LeaseRecord:
    authorization: authorization_owner.PinnedSyntheticRuntimeAuthorization
    lease_ref: ref
    projection_json: str
    lifecycle_state: str
    signature: str


@dataclass(frozen=True, slots=True)
class _OwnerStore:
    authorization_leases: dict
    leases: dict


_STORE = _OwnerStore({}, {})


def _projection(lease):
    projection = {}
    for item in fields(PinnedSyntheticRuntimeExecutionLease):
        value = getattr(lease, item.name, None)
        if item.name == "scenario":
            value = _scenario_projection(value)
        elif item.name == "provider":
            value = _provider_projection(value)
        elif item.name == "issuing_pid":
            if type(value) is not int or value != _ISSUER_PID:
                _fail("LEASE_UNAUTHENTICATED", "exact issuing PID required")
        elif item.name in _FALSE_AUTHORITY or item.name in (
                "lease_issued", "one_shot_exact_synthetic_activation_capability"):
            expected = item.name not in _FALSE_AUTHORITY
            if type(value) is not bool or value is not expected:
                _fail("LEASE_UNAUTHENTICATED", "immutable authority matrix required")
        elif type(value) is not str:
            _fail("LEASE_UNAUTHENTICATED", "exact lease string field required: " + item.name)
        projection[item.name] = value
    return projection


def _sign(projection_json, state):
    return hmac.new(_SECRET, _framed({"immutable_issuance_projection": projection_json,
        "current_state": state}, "lease-record-hmac"), "sha256").hexdigest()


def _unsigned_lease(authorization, lease_id):
    # Snapshot public projections only after authentication; retain upstream separately.
    scenario = authorization_owner.PinnedSyntheticScenarioIdentity(**{
        item.name: getattr(authorization.scenario, item.name)
        for item in fields(authorization_owner.PinnedSyntheticScenarioIdentity)})
    provider = authorization_owner.PinnedSyntheticProviderIdentity(**_provider_projection(authorization.provider))
    lease = PinnedSyntheticRuntimeExecutionLease(authorization.authorization_id,
        _authorization_fingerprint(authorization), authorization.proof_context_id, _ISSUER_PID,
        scenario, provider, ACTIVATION_POLICY_ID,
        _digest(_activation_policy(), "activation-policy"), lease_id, "", "")
    payload = _projection(lease)
    payload.pop("evidence_digest")
    payload.pop("stable_fingerprint")
    lease = replace(lease, evidence_digest=_digest(payload, "lease-evidence"))
    payload = _projection(lease)
    payload.pop("stable_fingerprint")
    return replace(lease, stable_fingerprint=_digest(payload, "lease-fingerprint"))


def _authenticated_record_locked(lease, authorization=None, *, require_authorization=False):
    if type(lease) is not PinnedSyntheticRuntimeExecutionLease or not _hex_id(getattr(lease, "lease_id", None)):
        _fail("LEASE_UNAUTHENTICATED", "exact original live pinned lease required")
    record = _STORE.leases.get(lease.lease_id)
    if type(record) is not _LeaseRecord or type(record.lease_ref) is not ref or record.lease_ref() is not lease:
        _fail("LEASE_UNAUTHENTICATED", "independent live owner identity required")
    if (require_authorization and authorization is None) or (
            authorization is not None and authorization is not record.authorization):
        _fail("LEASE_UNAUTHENTICATED", "supplied authorization must be the retained exact original")
    original = _authenticate_authorization(record.authorization)
    if _STORE.authorization_leases.get(_one_shot_key(original)) != lease.lease_id:
        _fail("LEASE_UNAUTHENTICATED", "permanent original authorization binding required")
    payload = _projection(lease)
    if payload["scenario"] != _scenario_projection(original.scenario):
        _fail("PINNED_AUTH_SCOPE_MISMATCH", "authenticated scenario projection changed")
    if payload["provider"] != _provider_projection(original.provider):
        _fail("PINNED_PROVIDER_PROVENANCE_MISMATCH", "authenticated provider projection changed")
    if (lease.activation_policy_identity != ACTIVATION_POLICY_ID
            or lease.activation_policy_digest != _digest(_activation_policy(), "activation-policy")
            or lease.scenario_phase_id != SCENARIO_PHASE_ID or lease.source_kind != SOURCE_KIND):
        _fail("PINNED_AUTH_SCOPE_MISMATCH", "exact scenario and activation policy scope required")
    expected = {"authorization_id": original.authorization_id,
        "authorization_fingerprint": _authorization_fingerprint(original),
        "authorization_proof_context_id": original.proof_context_id,
        "owner_identity": OWNER_ID, "phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION,
        "initial_state": ISSUED}
    if any(payload[name] != value for name, value in expected.items()):
        _fail("LEASE_UNAUTHENTICATED", "immutable original owner and upstream binding required")
    evidence = {name: value for name, value in payload.items()
        if name not in ("evidence_digest", "stable_fingerprint")}
    fingerprint = {name: value for name, value in payload.items() if name != "stable_fingerprint"}
    if (not _hex_id(lease.evidence_digest) or not _hex_id(lease.stable_fingerprint)
            or lease.evidence_digest != _digest(evidence, "lease-evidence")
            or lease.stable_fingerprint != _digest(fingerprint, "lease-fingerprint")
            or type(record.projection_json) is not str or _canonical(payload) != record.projection_json
            or type(record.lifecycle_state) is not str or record.lifecycle_state not in (ISSUED, CONSUMED, INVALIDATED)
            or not _hex_id(record.signature)
            or not hmac.compare_digest(record.signature, _sign(record.projection_json, record.lifecycle_state))):
        _fail("LEASE_UNAUTHENTICATED", "signed immutable projection and current state required")
    return record


def issue_pinned_synthetic_runtime_execution_lease(authorization):
    """One permanent issuance per publicly authenticated original authorization."""
    global _STORE
    with _local_lock(authorization):
        original = _authenticate_authorization(authorization)
        key = _one_shot_key(original)
        if key in _STORE.authorization_leases:
            _fail("DUPLICATE_LEASE_ISSUANCE", "authorization already has a permanent lease tombstone")
        lease_id = secrets.token_hex(32)
        if not _hex_id(lease_id):
            _fail("PROOF_UNRESOLVED", "owner lease identifier unavailable")
        while lease_id in _STORE.leases:
            lease_id = secrets.token_hex(32)
            if not _hex_id(lease_id):
                _fail("PROOF_UNRESOLVED", "owner lease identifier unavailable")
        lease = _unsigned_lease(original, lease_id)
        projection_json = _canonical(_projection(lease))
        record = _LeaseRecord(original, ref(lease), projection_json, ISSUED, _sign(projection_json, ISSUED))
        updated = _OwnerStore({**_STORE.authorization_leases, key: lease_id}, {**_STORE.leases, lease_id: record})
        _STORE = updated  # The only issuance publication/linearization point.
        return lease


def validate_pinned_synthetic_runtime_execution_lease(lease, authorization=None):
    with _local_lock(lease):
        _authenticated_record_locked(lease, authorization)
        return lease


def pinned_synthetic_runtime_execution_lease_state(lease, authorization=None):
    with _local_lock(lease):
        return _authenticated_record_locked(lease, authorization).lifecycle_state


def check_pinned_synthetic_runtime_execution_lease_preconditions(lease, authorization):
    """Authenticated report-only snapshot; never a reservation or consumer token."""
    with _local_lock(lease):
        record = _authenticated_record_locked(lease, authorization, require_authorization=True)
        reason = {ISSUED: "PROOF_UNRESOLVED", CONSUMED: "LEASE_ALREADY_CONSUMED",
            INVALIDATED: "LEASE_INVALIDATED"}[record.lifecycle_state]
        return PinnedSyntheticRuntimeExecutionLeaseReadiness(
            record.lifecycle_state == ISSUED, False, record.lifecycle_state, reason)


def _consumer_readiness():
    # No evidence owner/API/classification exists. No caller or test-only bypass.
    _fail("PROOF_UNRESOLVED", "separately reviewed pinned consumer/source/compile contract required")


def _transition(lease, authorization, target):
    global _STORE
    with _local_lock(lease):
        record = _authenticated_record_locked(lease, authorization, require_authorization=target == CONSUMED)
        if type(target) is not str or target not in (CONSUMED, INVALIDATED):
            _fail("LEASE_UNAUTHENTICATED", "unsupported terminal transition")
        if record.lifecycle_state != ISSUED:
            _fail("LEASE_ALREADY_CONSUMED" if record.lifecycle_state == CONSUMED else "LEASE_INVALIDATED")
        if target == CONSUMED:
            _consumer_readiness()
        updated_record = replace(record, lifecycle_state=target, signature=_sign(record.projection_json, target))
        updated = _OwnerStore(_STORE.authorization_leases, {**_STORE.leases, lease.lease_id: updated_record})
        _STORE = updated  # The only terminal publication/linearization point.
        return lease


def consume_pinned_synthetic_runtime_execution_lease(lease, authorization):
    """Fail closed until a separately reviewed consumer contract is implemented."""
    return _transition(lease, authorization, CONSUMED)


def invalidate_pinned_synthetic_runtime_execution_lease(lease, authorization=None):
    """Authenticate and terminate ISSUED without requiring behavioral readiness."""
    return _transition(lease, authorization, INVALIDATED)
