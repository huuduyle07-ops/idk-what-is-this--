"""SYNTH.AUTH.PINNED.1: one frozen scenario scope, never execution activation.

The no-argument issuer obtains one fresh public PINNED.1C proof in this process.
Its original root and complete graph remain retained and publicly authenticated
on every authorization validation. Reports, hashes and signatures cannot reload
either capability. The old SYNTH.AUTH.1 spec supplies source/scenario identities
only; its historical Java requirement and authorization epoch stay unchanged.
"""
from __future__ import annotations

from copy import copy, deepcopy
from dataclasses import asdict, dataclass, field, fields, replace
from hashlib import sha256
import hmac
import json
import os
import secrets
from types import SimpleNamespace
from unittest.mock import patch

from core import runtime_java_pinned_backend_target_binding as binding
from core import runtime_java_pinned_provider as provider_owner
from core.runtime.synthetic import synthetic_runtime_authorization as frozen_scenario
from core.runtime_java_pinned_requirement import REQUIREMENT

PHASE_ID = "SYNTH.AUTH.PINNED.1"
SCHEMA_VERSION = "synthetic_runtime_authorization_pinned_1_v1"
OWNER_ID = "core.synthetic_runtime_authorization_pinned"
COMPLETE = "SYNTH_AUTH_PINNED_1_COMPLETE"
BLOCKED = "SYNTH_AUTH_PINNED_1_BLOCKED"
_DOMAIN = b"CATTUS:SYNTH.AUTH.PINNED.1:exact-scenario-authorization:v1\x00"
_SECRET = secrets.token_bytes(32)
_ISSUER_PID = os.getpid()
_LIVE = {}
_FALSE_AUTHORITY = (
    "runtime_execution_authority", "execution_lease_authority",
    "reflection_execution_authority", "real_task_runtime_authority",
    "repository_write_authority", "apply_authority", "network_authority",
    "host_mount_authority", "shell_authority", "arbitrary_command_authority",
    "executor_authority", "BANK_authority", "arbitrary_java_authority",
    "arbitrary_class_authority", "arbitrary_method_authority",
    "arbitrary_source_authority", "repository_java_authority",
)
_ZERO_EFFECTS = (
    "SyntheticStateBox", "reflection_reads", "runtime_lease_consumption",
    "reflection_lease_consumption", "EXECUTOR.1R", "BANK", "Apply",
    "repository_runtime_writes", "behavioral_candidate_execution",
    "arbitrary_Java", "shell", "outbound_network", "host_mounts",
)


class PinnedSyntheticAuthorizationError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise PinnedSyntheticAuthorizationError(code, reason)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value, role):
    return sha256(_DOMAIN + role.encode() + b"\x00" + _canonical(value).encode()).hexdigest()


def _local_process():
    if os.getpid() != _ISSUER_PID:
        _fail("pinned_synthetic_authorization_unauthenticated", "issuing process required")


@dataclass(frozen=True, slots=True)
class PinnedSyntheticScenarioIdentity:
    scenario_id: str
    source_sha256: str
    source_size_bytes: int
    definition_sha256: str
    class_name: str
    method_name: str
    method_signature: str
    arguments: tuple[int, ...]
    argument_types: tuple[str, ...]
    return_type: str
    field_owner: str
    field_name: str
    field_type: str
    expected_before: int
    expected_return: bool
    expected_after: int


def _scenario_identity():
    spec = frozen_scenario.executor1r_decrement_3_spec()
    frozen_scenario.validate_synthetic_runtime_scenario_spec(spec)
    source = frozen_scenario.get_executor1r_decrement_3_source()
    if sha256(source).hexdigest() != spec.source_sha256 or len(source) != spec.source_size_bytes:
        _fail("frozen_synthetic_source_unrecoverable")
    invocation, observation = spec.invocation_contract, spec.observation_contract
    metadata = observation.requested_field_metadata
    # Signature is a rendering of the exact frozen contract, not a new method.
    signature = (invocation.return_type + " " + invocation.owner + "."
        + invocation.public_method + "(" + ",".join(invocation.argument_types) + ")")
    scenario = PinnedSyntheticScenarioIdentity(spec.scenario_id, spec.source_sha256,
        spec.source_size_bytes, metadata.definition_sha256, invocation.owner,
        invocation.public_method, signature, invocation.arguments, invocation.argument_types,
        invocation.return_type, metadata.owner, metadata.member, metadata.declared_type,
        observation.expected_before, observation.expected_return, observation.expected_after)
    return spec, scenario


@dataclass(frozen=True, slots=True)
class PinnedSyntheticProviderIdentity:
    phase_id: str
    schema_version: str
    owner_identity: str
    proof_context_identity: str
    receipt_id: str
    fingerprint: str
    evidence_digest: str
    requirement_profile: str
    requirement_schema: str
    target_image_identity: str
    runtime_sandbox_profile: str
    runtime_sandbox_policy_sha256: str
    controller_identity_evidence_json: str
    cleanup_evidence_json: str
    cleanup_evidence_digest: str


def _provider_objects(outcome):
    if type(outcome) is not provider_owner.ExactProviderOutcome:
        _fail("pinned_provider_original_outcome_required")
    graph = outcome.pinned_binding
    if type(graph) is not binding.BackendTargetBindingOutcome:
        _fail("pinned_provider_original_binding_required")
    return (graph.receipt, graph.bind_attachment, graph.sandbox_descriptor,
        graph.sandbox_receipt, graph.inspection_receipt, outcome.runtime_descriptor,
        outcome.runtime_receipt, outcome.sandbox_descriptor, outcome.sandbox_receipt,
        outcome.attachment)


def _authenticate_provider(outcome):
    if type(outcome) is not provider_owner.ExactProviderOutcome or outcome.status != provider_owner.COMPLETE:
        _fail("pinned_provider_incomplete", getattr(outcome, "reason", "live proof required"))
    objects = _provider_objects(outcome)
    root = provider_owner.validate_pinned_java_exact_provider(outcome.receipt, *objects)
    if (root is not outcome.receipt or root.phase_id != provider_owner.PHASE_ID
            or root.schema_version != provider_owner.SCHEMA_VERSION
            or root.status != provider_owner.COMPLETE or root.exact_provider_proven is not True
            or root.requirement_profile != REQUIREMENT.java_profile_id
            or root.requirement_schema != REQUIREMENT.java_schema_version
            or any(getattr(root, f.name) is not False for f in fields(root)
                if "authority" in f.name)):
        _fail("pinned_provider_proof_only_required")
    evidence = json.loads(root.evidence_json)
    spec, _ = _scenario_identity()
    if (evidence["target_image_identity"] != REQUIREMENT.image_identity
            or evidence["sandbox_policy_sha256"] != spec.sandbox_policy_sha256
            or outcome.sandbox_descriptor.schema_version != spec.sandbox_profile_id
            or evidence["cleanup"]["remaining_phase_containers"] != 0):
        _fail("pinned_provider_exact_requirement_required")
    controller_keys = (
        "target_controller_normalized_path", "target_controller_resolved_path",
        "target_controller_sha256", "target_controller_evidence_digest", "runtime_controller_path",
        "controller_runtime_identity_method", "runtime_controller_same_executable_proven",
        "runtime_controller_byte_rehash_performed", "controller_source_identity",
        "controller_source_coherent", "controller_invocation_digest", "runtime_configuration_digest",
        "runtime_image_metadata_digest", "runtime_controller_uid", "runtime_controller_gid",
        "runtime_readonly_root", "host_mounts_affecting_controller", "image_volumes_affecting_controller",
        "archive_ancestor_metadata_complete", "runtime_controller_traversal_confirmed",
    )
    identity = PinnedSyntheticProviderIdentity(root.phase_id, root.schema_version,
        root.owner_identity, root.proof_context_identity, root.receipt_id, root.fingerprint,
        root.evidence_digest, root.requirement_profile, root.requirement_schema,
        evidence["target_image_identity"], outcome.sandbox_descriptor.schema_version,
        evidence["sandbox_policy_sha256"], _canonical({k: evidence[k] for k in controller_keys}),
        _canonical(evidence["cleanup"]), evidence["cleanup_evidence_digest"])
    return root, objects, identity


@dataclass(frozen=True, slots=True)
class PinnedSyntheticRuntimeAuthorization:
    owner_identity: str
    authorization_id: str
    proof_context_id: str
    issuing_pid: int
    scenario: PinnedSyntheticScenarioIdentity
    provider: PinnedSyntheticProviderIdentity
    evidence_digest: str
    _signature: str = field(default="", repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    status: str = field(default=COMPLETE, init=False)
    synthetic_scenario_authorized: bool = field(default=True, init=False)
    runtime_execution_authority: bool = field(default=False, init=False)
    execution_lease_authority: bool = field(default=False, init=False)
    reflection_execution_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)
    shell_authority: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    executor_authority: bool = field(default=False, init=False)
    BANK_authority: bool = field(default=False, init=False)
    arbitrary_java_authority: bool = field(default=False, init=False)
    arbitrary_class_authority: bool = field(default=False, init=False)
    arbitrary_method_authority: bool = field(default=False, init=False)
    arbitrary_source_authority: bool = field(default=False, init=False)
    repository_java_authority: bool = field(default=False, init=False)
    execution_lease_issued: bool = field(default=False, init=False)
    lifecycle_compatibility_evaluated: bool = field(default=False, init=False)
    lifecycle_execution_ready: bool = field(default=False, init=False)
    reflection_admission_issued: bool = field(default=False, init=False)
    scenario_executed: bool = field(default=False, init=False)
    measured_runtime_outcome: bool = field(default=False, init=False)

    @property
    def fingerprint(self):
        validate_pinned_synthetic_runtime_authorization(self)
        return _digest(_payload(self), "authorization-fingerprint")

    def as_dict(self):
        validate_pinned_synthetic_runtime_authorization(self)
        return {**_payload(self), "authorization_fingerprint": self.fingerprint, "report_only": True}


def _payload(authorization):
    return {f.name: asdict(getattr(authorization, f.name))
        if f.name in ("scenario", "provider") else getattr(authorization, f.name)
        for f in fields(PinnedSyntheticRuntimeAuthorization) if f.name != "_signature"}


def _evidence_digest(authorization):
    payload = _payload(authorization)
    payload.pop("evidence_digest")
    return _digest(payload, "authorization-evidence")


def _sign(authorization):
    return hmac.new(_SECRET, _DOMAIN + b"authorization-hmac\x00"
        + _canonical(_payload(authorization)).encode(), "sha256").hexdigest()


def _exact_shape(value, template):
    if type(value) is not type(template):
        return False
    if type(template) in (PinnedSyntheticRuntimeAuthorization,
            PinnedSyntheticScenarioIdentity, PinnedSyntheticProviderIdentity):
        return all(_exact_shape(getattr(value, f.name), getattr(template, f.name))
            for f in fields(template) if f.name != "_signature")
    if type(template) is tuple:
        return len(value) == len(template) and all(_exact_shape(v, t) for v, t in zip(value, template))
    return value == template


def validate_pinned_synthetic_runtime_authorization(authorization, *, provider_outcome=None):
    """Validate scope and the original live proof; this never activates execution."""
    _local_process()
    if type(authorization) is not PinnedSyntheticRuntimeAuthorization:
        _fail("pinned_synthetic_authorization_unauthenticated", "original new epoch handle required")
    if type(authorization.authorization_id) is not str:
        _fail("pinned_synthetic_authorization_unauthenticated")
    record = _LIVE.get(authorization.authorization_id)
    if (record is None or record["object"] is not authorization
            or type(authorization.issuing_pid) is not int or authorization.issuing_pid != _ISSUER_PID
            or (provider_outcome is not None and provider_outcome is not record["provider_outcome"])):
        _fail("pinned_synthetic_authorization_unauthenticated", "live original process and graph required")
    spec, scenario = _scenario_identity()
    root, objects, provider = _authenticate_provider(record["provider_outcome"])
    if (spec is not record["spec"] or root is not record["provider_root"]
            or record["provider_outcome"].pinned_binding is not record["provider_binding"]
            or any(actual is not original for actual, original in zip(objects, record["provider_objects"]))):
        _fail("pinned_synthetic_provider_graph_mismatch")
    expected = PinnedSyntheticRuntimeAuthorization(OWNER_ID, record["authorization_id"],
        record["proof_context_id"], _ISSUER_PID, scenario, provider, "")
    expected = replace(expected, evidence_digest=_evidence_digest(expected))
    if not _exact_shape(authorization, expected) or _canonical(_payload(authorization)) != record["canonical"]:
        _fail("pinned_synthetic_authorization_scope_mismatch")
    if (type(authorization._signature) is not str or len(authorization._signature) != 64
            or any(c not in "0123456789abcdef" for c in authorization._signature)
            or not hmac.compare_digest(authorization._signature, _sign(authorization))):
        _fail("pinned_synthetic_authorization_unauthenticated", "independent process-local HMAC required")
    return authorization


@dataclass(frozen=True, slots=True)
class PinnedSyntheticAuthorizationOutcome:
    status: str
    reason: str
    authorization: PinnedSyntheticRuntimeAuthorization | None
    provider_outcome: provider_owner.ExactProviderOutcome | None
    _report: dict = field(repr=False, compare=False)

    def as_dict(self):
        return deepcopy(self._report)


def issue_pinned_synthetic_runtime_authorization():
    """One fresh provider attempt and one exact scope grant; no free-form input."""
    _local_process()
    # Frozen identities must be recoverable before any provider effects occur.
    spec, scenario = _scenario_identity()
    report = {"phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION, "owner_identity": OWNER_ID,
        "status": BLOCKED, "reason": "authorization_not_issued", "scenario": asdict(scenario),
        "synthetic_scenario_authorized": False, **dict.fromkeys(_FALSE_AUTHORITY, False),
        "execution_lease_issued": False, "lifecycle_compatibility_evaluated": False,
        "lifecycle_execution_ready": False, "reflection_admission_issued": False,
        "SyntheticStateBox_executed": False, "measured_observations": None,
        "authorization_scope_is_execution_lease": False, "provider_proof_consumed": False,
        "provider_proof_fallback": False, "provider_proof_issuance_attempts": 1,
        "exported_json_is_report_only": True, "authorization_authentication": None,
        "authorization_owner_local_effects": {"authorizations_issued": 0, "live_registry_entries_added": 0,
            "processes_created": 0, "containers_created": 0, "source_files_created": 0},
        "forbidden_effect_counts": dict.fromkeys(_ZERO_EFFECTS, 0)}
    authorization = outcome = None
    try:
        outcome = provider_owner.issue_pinned_java_exact_provider()
        provider_report = outcome.as_dict()
        report["provider_proof_report"] = provider_report
        report["provider_proof_status"] = outcome.status
        bound = provider_report.get("pinned1b_report", {})
        report["provider_proof_infrastructure_effects"] = provider_report.get(
            "operational_effect_counts_by_owner", {
                "runtime_backend_effects": provider_report.get("runtime_backend_effects", {}),
                "PINNED1A": bound.get("target_inspection_report", {}).get("operational_effect_counts", {}),
                **{k: bound.get(k, {}) for k in (
                    "bind_pre_effects", "bind_post_effects", "bind_sandbox2_infrastructure_effects")}})
        report["remaining_phase_containers"] = provider_report.get("remaining_phase_containers")
        report["cleanup_verified"] = provider_report.get("cleanup_verified", False)
        root, objects, provider = _authenticate_provider(outcome)
        unsigned = PinnedSyntheticRuntimeAuthorization(OWNER_ID, secrets.token_hex(32),
            secrets.token_hex(32), _ISSUER_PID, scenario, provider, "")
        unsigned = replace(unsigned, evidence_digest=_evidence_digest(unsigned))
        authorization = replace(unsigned, _signature=_sign(unsigned))
        _LIVE[authorization.authorization_id] = {"object": authorization, "spec": spec,
            "provider_outcome": outcome, "provider_root": root, "provider_objects": objects,
            "provider_binding": outcome.pinned_binding,
            "authorization_id": authorization.authorization_id, "proof_context_id": authorization.proof_context_id,
            "canonical": _canonical(_payload(authorization))}
        validate_pinned_synthetic_runtime_authorization(authorization)
        report.update(status=COMPLETE, reason="exact_frozen_scenario_authorized_for_authenticated_pinned_provider",
            synthetic_scenario_authorized=True, synthetic_authorization=authorization.as_dict(),
            authorization_id=authorization.authorization_id, authorization_fingerprint=authorization.fingerprint,
            provider_proof_id=root.receipt_id, provider_proof_fingerprint=root.fingerprint,
            provider_requirement_profile=root.requirement_profile, provider_requirement_schema=root.requirement_schema,
            provider_exact_provider_proven=root.exact_provider_proven,
            provider_authority_false_matrix={f.name: getattr(root, f.name) for f in fields(root) if "authority" in f.name},
            authorization_authentication={"authenticated_in_issuing_process": True,
                "independent_domain_separated_HMAC_SHA256": True, "exact_live_object_retained": True,
                "exact_original_provider_graph_retained": True, "public_PINNED_1C_validator_used": True,
                "HMAC_or_capability_persisted": False},
            authorization_owner_local_effects={"authorizations_issued": 1, "live_registry_entries_added": 1,
                "processes_created": 0, "containers_created": 0, "source_files_created": 0})
    except (PinnedSyntheticAuthorizationError, provider_owner.PinnedProviderBlocked,
            ValueError, TypeError, KeyError, AttributeError, OSError) as error:
        if authorization is not None:
            _LIVE.pop(authorization.authorization_id, None)
        authorization = None
        report.update(status=BLOCKED, reason="authorization_prerequisite_failed:" + str(error)[:300])
    report["stop_boundary"] = "Authorization issuance only. Lifecycle compatibility and execution require a separate phase."
    return PinnedSyntheticAuthorizationOutcome(report["status"], report["reason"], authorization, outcome, report)


def negative_authentication_matrix(outcome):
    """Pure reversible rejection controls on one issuance, with no new proof."""
    authorization = outcome.authorization
    validate_pinned_synthetic_runtime_authorization(authorization)
    results = {}

    def rejected(candidate=authorization, **kwargs):
        try:
            validate_pinned_synthetic_runtime_authorization(candidate, **kwargs)
        except (ValueError, TypeError, AttributeError):
            return True
        return False

    for name, candidate in (("copy", copy(authorization)), ("deepcopy", deepcopy(authorization)),
            ("dataclasses_replace", replace(authorization)), ("JSON", authorization.as_dict()),
            ("wrapper", SimpleNamespace(**authorization.as_dict()))):
        results[name] = rejected(candidate)
    decoded = json.loads(_canonical(_payload(authorization)))
    decoded["scenario"]["arguments"] = tuple(decoded["scenario"]["arguments"])
    decoded["scenario"]["argument_types"] = tuple(decoded["scenario"]["argument_types"])
    decoded["scenario"] = PinnedSyntheticScenarioIdentity(**decoded["scenario"])
    decoded["provider"] = PinnedSyntheticProviderIdentity(**decoded["provider"])
    constructor = {f.name: decoded[f.name] for f in fields(authorization) if f.init and f.name != "_signature"}
    results["JSON_reconstruction"] = rejected(PinnedSyntheticRuntimeAuthorization(
        **constructor, _signature=authorization._signature))
    class Subclass(PinnedSyntheticRuntimeAuthorization):
        pass
    results["subclass"] = rejected(Subclass(**constructor))
    old = frozen_scenario.issue_synthetic_runtime_authorization(
        frozen_scenario.executor1r_decrement_3_spec(), source=frozen_scenario.get_executor1r_decrement_3_source())
    results["old_SYNTH_AUTH_1_handle"] = rejected(old)
    with patch.object(os, "getpid", return_value=os.getpid() + 1):
        results["wrong_process"] = rejected()
    with patch(__name__ + "._SECRET", secrets.token_bytes(32)):
        results["wrong_HMAC_key"] = rejected()

    def changed_field(obj, name, changed, label):
        original = getattr(obj, name)
        try:
            object.__setattr__(obj, name, changed)
            results[label] = rejected()
        finally:
            object.__setattr__(obj, name, original)

    for name, changed in {"_signature": "0" * 64, "issuing_pid": -1,
            "owner_identity": "caller-alias", "proof_context_id": "0" * 64,
            "evidence_digest": "0" * 64, **dict.fromkeys(_FALSE_AUTHORITY, True)}.items():
        changed_field(authorization, name, changed, "authorization_" + name)
    for name in (f.name for f in fields(authorization.scenario)):
        value = getattr(authorization.scenario, name)
        changed = not value if type(value) is bool else value + 1 if type(value) is int else (
            (4,) if name == "arguments" else ("caller-type",) if type(value) is tuple else value + "_changed")
        changed_field(authorization.scenario, name, changed, "scenario_" + name)
    for name in (f.name for f in fields(authorization.provider)):
        changed_field(authorization.provider, name, "caller-alias", "provider_projection_" + name)
    changed_field(authorization.provider, "requirement_profile", "RUNTIME.JAVA.1", "old_JAVA_1_requirement")
    changed_field(authorization.provider, "requirement_schema", "runtime_java_1_v1", "old_JAVA_1_schema")
    proof = outcome.provider_outcome
    results["different_provider_root"] = rejected(provider_outcome=replace(proof, receipt=copy(proof.receipt)))
    results["different_provider_outcome"] = rejected(provider_outcome=replace(proof))
    results["historical_PINNED_1C_JSON"] = rejected(provider_outcome=proof.as_dict())
    results["chronology_only_provider_relation"] = rejected(provider_outcome=SimpleNamespace(status=provider_owner.COMPLETE))
    for name in ("receipt", "pinned_binding", "runtime_descriptor", "runtime_receipt",
            "sandbox_descriptor", "sandbox_receipt", "attachment"):
        original = getattr(proof, name)
        changed_field(proof, name, copy(original), "retained_provider_" + name + "_copy")
    changed_field(proof, "receipt", proof.receipt.as_dict(), "retained_provider_root_report_JSON")
    graph = proof.pinned_binding
    for name in ("receipt", "bind_attachment", "sandbox_descriptor", "sandbox_receipt", "inspection_receipt"):
        changed_field(graph, name, copy(getattr(graph, name)), "retained_binding_" + name + "_copy")
    for name, changed in {"receipt_id": "0" * 64, "proof_context_identity": "0" * 64,
            "evidence_digest": "0" * 64, "exact_provider_proven": False,
            "runtime_authority": True, "SYNTH_authority": True,
            "requirement_profile": "caller-alias", "requirement_schema": "caller-alias"}.items():
        changed_field(proof.receipt, name, changed, "provider_root_" + name)
    validate_pinned_synthetic_runtime_authorization(authorization)
    return results
