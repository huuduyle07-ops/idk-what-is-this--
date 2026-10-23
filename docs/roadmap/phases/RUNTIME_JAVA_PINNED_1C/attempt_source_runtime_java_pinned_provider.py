"""PINNED.1C exact provider proof; infrastructure evidence, never a lease.

The sole operational entry point has no inputs. It invokes the frozen public
owners once and observes JAVA.1C return frames without changing their code,
validators, receipts or commands. The observer retains its actual sandbox pair;
report projections are never reconstructed as provenance. Controller identity
uses the complete target byte measurement and the permitted immutable-image
relation, rather than claiming a second controller byte measurement.
"""
from copy import copy, deepcopy
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import hmac
import json
import os
import secrets
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from core import candidate_runtime_sandbox as sandbox
from core import runtime_java_pinned_backend_target_binding as pinned
from core import sandbox_backend_binding as backend
from core import sandboxed_java_positive_continuation as runtime
from core import thread_compatible_runtime_sandbox as sandbox2
from core.runtime_java_pinned_requirement import REQUIREMENT

PHASE_ID = "RUNTIME.JAVA.PINNED.1C"
SCHEMA_VERSION = "runtime_java_pinned_provider_1c_v1"
OWNER_ID = "core.runtime_java_pinned_provider"
COMPLETE = "RUNTIME_JAVA_PINNED_1C_COMPLETE"
BACKEND_MISMATCH = "PINNED_BACKEND_BINDING_MISMATCH"
RUNTIME_MISMATCH = "PINNED_RUNTIME_EVIDENCE_MISMATCH"
CONTROLLER_MISMATCH = "PINNED_CONTROLLER_MISMATCH"
CLEANUP_FAILURE = "PINNED_CLEANUP_FAILURE"
UNRESOLVED = "PINNED_PROOF_UNRESOLVED"
CONTROLLER_RESOLVED = "/usr/local/bin/python3.12"
CONTROLLER_SHA256 = "0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263"
_DOMAIN = b"CATTUS:RUNTIME.JAVA.PINNED.1C:exact-provider:v1\x00"
_SECRET = secrets.token_bytes(32)
_LIVE, _ATTACHMENTS, _ATTEMPTS, _ORIGINS = {}, {}, {}, {}
_VERIFY_CODE, _INVOKE_CODE = runtime.verify.__code__, runtime._invoke.__code__
_FALSE_CLAIMS = ("runtime_authority", "real_task_runtime_authority",
    "repository_write_authority", "apply_authority", "compatibility_authority",
    "SYNTH_authority", "executor_authority", "complete_inventory_claimed",
    "complete_local_artifact_discovery_claimed", "global_provider_absence_claimed",
    "global_provider_uniqueness_claimed", "daemon_identity_claimed",
    "daemon_continuity_claimed", "aba_resistance_claimed", "daemon_identity_proven",
    "daemon_continuity_proven", "aba_resistance_proven")
_ZERO_EFFECTS = ("BANK", "SyntheticStateBox", "behavioral_Java_candidate", "reflection",
    "runtime_lease_consumption", "reflection_lease_consumption", "EXECUTOR.1R", "Apply",
    "repository_runtime_writes", "pulls", "builds", "generic_image_inventory",
    "alternative_provider_inspection", "outbound_workload_network", "host_mounts", "caller_shell")


class PinnedProviderBlocked(ValueError):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status, self.reason = status, reason


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value, role="evidence"):
    return sha256(_DOMAIN + role.encode() + b"\x00" + _canonical(value).encode()).hexdigest()


def _payload(value):
    data = asdict(value)
    data.pop("_signature")
    return data


def _sign(value):
    return hmac.new(_SECRET, _DOMAIN + type(value).__name__.encode() + b"\x00"
        + _canonical(_payload(value)).encode(), "sha256").hexdigest()


def _evidence_digest(value, role):
    payload = _payload(value)
    payload.pop("evidence_digest")
    return _digest(payload, role)


@dataclass(frozen=True, slots=True)
class RuntimeProviderAttachment:
    owner_identity: str
    proof_context_identity: str
    receipt_id: str
    issuing_pid: int
    evidence_json: str
    evidence_digest: str
    _signature: str = field(default="", repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION + ":runtime_attachment", init=False)
    status: str = field(default=COMPLETE, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    compatibility_authority: bool = field(default=False, init=False)
    SYNTH_authority: bool = field(default=False, init=False)
    executor_authority: bool = field(default=False, init=False)
    complete_inventory_claimed: bool = field(default=False, init=False)
    complete_local_artifact_discovery_claimed: bool = field(default=False, init=False)
    global_provider_absence_claimed: bool = field(default=False, init=False)
    global_provider_uniqueness_claimed: bool = field(default=False, init=False)
    daemon_identity_claimed: bool = field(default=False, init=False)
    daemon_continuity_claimed: bool = field(default=False, init=False)
    aba_resistance_claimed: bool = field(default=False, init=False)
    daemon_identity_proven: bool = field(default=False, init=False)
    daemon_continuity_proven: bool = field(default=False, init=False)
    aba_resistance_proven: bool = field(default=False, init=False)
    exact_provider_proven: bool = field(default=False, init=False)

    @property
    def fingerprint(self):
        return _digest(_payload(self), "runtime-attachment-fingerprint")

    def as_dict(self):
        return {**_payload(self), "evidence": json.loads(self.evidence_json),
            "fingerprint": self.fingerprint, "report_only": True}


@dataclass(frozen=True, slots=True)
class PinnedJavaExactProviderReceipt:
    requirement_profile: str
    requirement_schema: str
    owner_identity: str
    proof_context_identity: str
    receipt_id: str
    issuing_pid: int
    evidence_json: str
    evidence_digest: str
    _signature: str = field(default="", repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    status: str = field(default=COMPLETE, init=False)
    exact_provider_proven: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    compatibility_authority: bool = field(default=False, init=False)
    SYNTH_authority: bool = field(default=False, init=False)
    executor_authority: bool = field(default=False, init=False)
    complete_inventory_claimed: bool = field(default=False, init=False)
    complete_local_artifact_discovery_claimed: bool = field(default=False, init=False)
    global_provider_absence_claimed: bool = field(default=False, init=False)
    global_provider_uniqueness_claimed: bool = field(default=False, init=False)
    daemon_identity_claimed: bool = field(default=False, init=False)
    daemon_continuity_claimed: bool = field(default=False, init=False)
    aba_resistance_claimed: bool = field(default=False, init=False)
    daemon_identity_proven: bool = field(default=False, init=False)
    daemon_continuity_proven: bool = field(default=False, init=False)
    aba_resistance_proven: bool = field(default=False, init=False)

    @property
    def fingerprint(self):
        return _digest(_payload(self), "exact-provider-fingerprint")

    def as_dict(self):
        return {**_payload(self), "evidence": json.loads(self.evidence_json),
            "fingerprint": self.fingerprint, "report_only": True}


@dataclass(frozen=True, slots=True)
class ExactProviderOutcome:
    status: str
    reason: str
    receipt: PinnedJavaExactProviderReceipt | None
    pinned_binding: pinned.BackendTargetBindingOutcome | None
    runtime_descriptor: runtime.JavaContinuationDescriptor | None
    runtime_receipt: runtime.JavaContinuationReceipt | None
    sandbox_descriptor: sandbox2.ThreadCompatibleSandboxDescriptor | None
    sandbox_receipt: sandbox2.ThreadCompatibleSandboxReceipt | None
    attachment: RuntimeProviderAttachment | None
    _report: dict = field(repr=False, compare=False)

    def as_dict(self):
        return deepcopy(self._report)


def _pinned_objects(value):
    if type(value) is not pinned.BackendTargetBindingOutcome:
        raise PinnedProviderBlocked(BACKEND_MISMATCH, "original_public_pinned1b_outcome_required")
    return (value.receipt, value.bind_attachment, value.sandbox_descriptor,
        value.sandbox_receipt, value.inspection_receipt)


def _authenticate_pinned(objects):
    try:
        pinned.validate_pinned_backend_target_binding(*objects)
    except pinned.PinnedBindingBlocked as error:
        raise PinnedProviderBlocked(error.status, "pinned1b_authentication:" + str(error)) from error
    receipt = objects[0]
    if (receipt.binding_result is not True or receipt.requirement_profile != REQUIREMENT.java_profile_id
            or receipt.requirement_schema != REQUIREMENT.java_schema_version
            or receipt.target_image_identity != REQUIREMENT.image_identity):
        raise PinnedProviderBlocked(BACKEND_MISMATCH, "exact_frozen_pinned1b_graph_required")


def _fixed_route():
    prefix, endpoint = sandbox._docker_prefix(), sandbox._local_endpoint()
    if (not endpoint or len(prefix) != 5 or prefix[1] != "--config"
            or prefix[3:] != ("--host", endpoint)):
        raise PinnedProviderBlocked(BACKEND_MISMATCH, "frozen_local_docker_route_unavailable")
    return prefix, endpoint


def _measure_backend(prefix, endpoint, calls):
    capture = sandbox._bounded_process((*prefix, "version", "--format", "{{json .}}"),
        timeout_ms=8000, stdout_limit=65536)
    calls.append({"command": "version", "completed": capture.status == "sandbox_completed",
        "exit_code": capture.exit_code, "control_reaped_and_pipes_closed":
        capture.status in ("sandbox_completed", "sandbox_timeout", "sandbox_output_limit_exceeded")})
    if not calls[-1]["control_reaped_and_pipes_closed"]:
        raise PinnedProviderBlocked(CLEANUP_FAILURE, "runtime_backend_control_cleanup_unproven")
    if (capture.status != "sandbox_completed" or capture.exit_code != 0
            or capture.termination_within_deadline is not True):
        raise PinnedProviderBlocked(BACKEND_MISMATCH, "runtime_backend_measurement_failed")
    try:
        value = json.loads(capture.stdout)
        server = value["Server"]
        if (type(value) is not dict or type(server) is not dict or server.get("Os") != "linux"
                or type(server.get("Version")) is not str or not server["Version"]):
            raise ValueError("exact_linux_server_version_required")
        return ("local-docker:" + endpoint, server["Version"])
    except (ValueError, TypeError, KeyError) as error:
        raise PinnedProviderBlocked(BACKEND_MISMATCH, "runtime_backend_measurement_invalid") from error


def _runtime_snapshot():
    """Read-only observation; exact return-frame originals, never report imports.

Only fixed code objects are observed. No frame local, argument, return value,
owner function or validator is replaced. A preexisting profiler blocks before
runtime issuance, avoiding interference with an external instrumentation owner.
    """
    previous = sys.getprofile()
    if previous is not None:
        raise PinnedProviderBlocked(UNRESOLVED, "runtime_observer_profile_already_owned")
    observed, controls = {"verify": [], "invoke": []}, []
    control_code = sandbox._bounded_process.__code__

    def observer(frame, event, result):
        if event != "return":
            return
        code = frame.f_code
        if code is _VERIFY_CODE:
            observed["verify"].append({key: frame.f_locals.get(key) for key in
                ("sd", "sr", "metadata", "prefix", "facts", "count", "report")})
            observed["verify"][-1]["result"] = result
        elif code is _INVOKE_CODE:
            observed["invoke"].append({key: frame.f_locals.get(key) for key in
                ("prefix", "name", "inspected", "capture", "facts", "cleanup", "inspected_ok")})
            observed["invoke"][-1]["result"] = result
        elif code is control_code:
            argv = frame.f_locals.get("argv", ())
            scope, caller = "JAVA1C_controls", frame.f_back
            while caller is not None:
                if caller.f_code is _INVOKE_CODE:
                    scope = "JAVA1C_fixed_controller"
                    break
                if caller.f_code in (sandbox2.invoke.__code__, sandbox2.replay.__code__):
                    scope = "JAVA1C_SANDBOX2_infrastructure"
                    break
                caller = caller.f_back
            controls.append({"argv": list(argv), "command": argv[5] if len(argv) > 5 else "",
                "scope": scope,
                "exit_code": getattr(result, "exit_code", None),
                "completed": getattr(result, "status", None) == "sandbox_completed",
                "control_reaped_and_pipes_closed": getattr(result, "status", None) in
                ("sandbox_completed", "sandbox_timeout", "sandbox_output_limit_exceeded")})

    try:
        sys.setprofile(observer)
        result = runtime.verify()
    finally:
        sys.setprofile(previous)
    if len(observed["verify"]) != 1 or len(observed["invoke"]) > 1:
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "actual_runtime_owner_observation_missing_or_ambiguous")
    observed.update(result=result, controls=controls)
    return observed


def _check_runtime(objects, measurement):
    jd, jr, sd, sr = objects
    try:
        runtime.validate_descriptor(jd, jr)
        runtime.authenticate_sandbox2(sd, sr)
    except (ValueError, TypeError, AttributeError) as error:
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "actual_runtime_owner_authentication_failed") from error
    if (jd.phase_id != "RUNTIME.JAVA.1C" or jr.phase_id != "RUNTIME.JAVA.1C"
            or jd.schema_version != "runtime_java_1c_v1" or jr.schema_version != "runtime_java_1c_v1"
            or sd.phase_id != "RUNTIME.SANDBOX.2" or sr.phase_id != "RUNTIME.SANDBOX.2"
            or sd.schema_version != "runtime_sandbox_2_v1" or sr.schema_version != "runtime_sandbox_2_v1"
            or jd.sandbox_descriptor_fingerprint != sd.fingerprint
            or jd.sandbox_receipt_fingerprint != sr.fingerprint
            or jr.sandbox_descriptor_fingerprint != sd.fingerprint or jr.sandbox_receipt_fingerprint != sr.fingerprint
            or jr.image_identity != REQUIREMENT.image_identity
            or jr.seccomp_policy_sha256 != REQUIREMENT.sandbox_policy_sha256
            or any(getattr(value, key) is not False for value in objects for key in sandbox2.AUTHORITIES)):
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "exact_actual_java1c_sandbox_pair_required")
    report, facts = measurement["runtime_report"], measurement["facts"]
    cleanup = {key: report.get(key) for key in ("cleanup_verified", "container_cleanup_verified",
        "child_and_capture_cleanup_verified", "temporary_workspace_removed", "phase_container_count_after_teardown")}
    if (jr.cleanup_verified is not True or any(cleanup[key] is not True for key in cleanup
            if key != "phase_container_count_after_teardown")
            or type(cleanup["phase_container_count_after_teardown"]) is not int
            or cleanup["phase_container_count_after_teardown"] != 0
            or sr.cleanup_verified is not True
            or any(row["control_reaped_and_pipes_closed"] is not True
                for row in (*measurement["controls"], *measurement["backend_controls"]))):
        raise PinnedProviderBlocked(CLEANUP_FAILURE, "all_actual_runtime_and_control_cleanup_required")
    digest = sandbox._hash({"facts": facts, "cleanup_verified": report["cleanup_verified"],
        "inspected_configuration_verified": report["inspected_configuration_verified"],
        "remaining_phase_containers": report["phase_container_count_after_teardown"],
        "temporary_workspace_removed": report["temporary_workspace_removed"]})
    if digest != jr.evidence_sha256 or sandbox._hash(report["live_sandbox2"]["stages"]) != sr.evidence_sha256:
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "full_runtime_or_actual_sandbox_evidence_digest_mismatch")
    if (report["status"] != runtime.COMPLETE or report["inspected_configuration_verified"] is not True
            or report["outer_capture_status"] != "sandbox_completed" or report["outer_exit_code"] != 0):
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "successful_frozen_java1c_required")
    return cleanup


def _runtime_evidence(upstreams, measurement):
    pr, bind, bind_sd, bind_sr, inspection, jd, jr, sd, sr = upstreams
    _authenticate_pinned(upstreams[:5])
    cleanup = _check_runtime(upstreams[5:], measurement)
    pre, post = measurement["pre"], measurement["post"]
    route, version = pr.canonical_backend_route_identity, pr.canonical_backend_server_version
    if (pre != post or pre != [route, version]
            or measurement["prefix"] != measurement["runtime_prefix"]
            or measurement["prefix"] != measurement["invoke_prefix"]
            or route != "local-docker:" + measurement["prefix"][4]
            or not measurement["controls"]
            or any(row["argv"][:5] != measurement["prefix"] for row in measurement["controls"])):
        raise PinnedProviderBlocked(BACKEND_MISMATCH, "actual_runtime_pair_backend_bridge_mismatch")
    facts, config, metadata = measurement["facts"], measurement["configuration"], measurement["metadata"]
    if (config.get("Image") != REQUIREMENT.image_identity or metadata.get("Id") != REQUIREMENT.image_identity
            or metadata.get("Os") != "linux" or metadata.get("Architecture") != "amd64"
            or metadata.get("Config", {}).get("Volumes") or not runtime.safe_configuration(config)):
        raise PinnedProviderBlocked(CONTROLLER_MISMATCH, "immutable_runtime_controller_root_configuration_required")
    controller = inspection.archive.controller
    if (controller.normalized_path != REQUIREMENT.controller.path
            or controller.resolved_path != CONTROLLER_RESOLVED or controller.sha256 != CONTROLLER_SHA256
            or controller.linux_amd64_elf is not True or controller.nonroot_executable is not True):
        raise PinnedProviderBlocked(CONTROLLER_MISMATCH, "exact_target_controller_byte_identity_required")
    settings, host = config["Config"], config["HostConfig"]
    if (settings["Entrypoint"] != [controller.normalized_path] or settings["User"] != "65534:65534"
            or host["ReadonlyRootfs"] is not True or host.get("Binds") or host.get("Mounts") or config.get("Mounts")):
        raise PinnedProviderBlocked(CONTROLLER_MISMATCH, "runtime_controller_same_immutable_executable_relation_missing")
    source = settings["Cmd"][4].encode()
    source_identity = dict(inspection.controller_source_identity)
    if (source_identity.get("phase_id") != runtime.PHASE_ID
            or source_identity.get("source_sha256") != sha256(source).hexdigest()
            or source_identity.get("source_size_bytes") != str(len(source))
            or source != runtime.probe.source().encode()):
        raise PinnedProviderBlocked(CONTROLLER_MISMATCH, "actual_frozen_controller_source_identity_mismatch")
    for role, expected in (("java", REQUIREMENT.java), ("javac", REQUIREMENT.javac)):
        measured = getattr(inspection.archive, role)
        if (measured.normalized_path != expected.path or measured.sha256 != expected.sha256
                or getattr(jr, role + "_path") != measured.normalized_path
                or getattr(jr, role + "_sha256") != measured.sha256
                or facts.get(role + "_binary_sha256") != measured.sha256):
            raise PinnedProviderBlocked(RUNTIME_MISMATCH, "target_and_runtime_" + role + "_mismatch")
    before, after = facts["controller_before"], facts["controller_after"]
    if (not runtime._state_safe(before) or not runtime._state_safe(after)
            or before["boundary"] != after["boundary"] or facts["phase_pids_after_cleanup"] != [1]):
        raise PinnedProviderBlocked(CONTROLLER_MISMATCH, "runtime_nonroot_controller_traversal_unconfirmed")
    # Preserve separate pair identities. Equality is neither a gate nor proof.
    return {"target_image_identity": REQUIREMENT.image_identity,
        "pinned1b_receipt_id": pr.receipt_id, "pinned1b_receipt_fingerprint": pr.fingerprint,
        "pinned1b_evidence_digest": pr.evidence_digest,
        "bind_attachment_id": bind.attachment_id, "bind_attachment_fingerprint": bind.fingerprint,
        "bind_sandbox_descriptor_fingerprint": bind_sd.fingerprint,
        "bind_sandbox_receipt_fingerprint": bind_sr.fingerprint,
        "bind_sandbox_evidence_digest": bind_sr.evidence_sha256,
        "inspection_owner_identity": inspection.owner_identity,
        "inspection_proof_context_identity": inspection.proof_context_identity,
        "inspection_receipt_id": inspection.receipt_id, "inspection_receipt_fingerprint": inspection.fingerprint,
        "inspection_evidence_digest": inspection.evidence_digest,
        "inspection_cleanup_digest": inspection.cleanup_evidence_digest,
        "canonical_backend_route": route, "canonical_backend_version": version,
        "runtime_backend_pre": pre, "runtime_backend_post": post,
        "cross_pair_bridge_result": True, "cross_pair_fingerprint_equality_required": False,
        "runtime_sandbox_descriptor_fingerprint": sd.fingerprint,
        "runtime_sandbox_receipt_fingerprint": sr.fingerprint, "runtime_sandbox_evidence_digest": sr.evidence_sha256,
        "runtime_descriptor_fingerprint": jd.fingerprint, "runtime_receipt_fingerprint": jr.fingerprint,
        "runtime_evidence_digest": jr.evidence_sha256, "runtime_image_identity": jr.image_identity,
        "sandbox_policy_sha256": sr.seccomp_policy_sha256,
        "target_java_path": inspection.archive.java.normalized_path, "target_java_sha256": inspection.archive.java.sha256,
        "runtime_java_path": jr.java_path, "runtime_java_sha256": facts["java_binary_sha256"],
        "target_javac_path": inspection.archive.javac.normalized_path, "target_javac_sha256": inspection.archive.javac.sha256,
        "runtime_javac_path": jr.javac_path, "runtime_javac_sha256": facts["javac_binary_sha256"],
        "image_coherent": True, "java_coherent": True, "javac_coherent": True,
        "target_controller_normalized_path": controller.normalized_path,
        "target_controller_resolved_path": controller.resolved_path, "target_controller_sha256": controller.sha256,
        "target_controller_evidence_digest": pr.inspection_controller_evidence_digest,
        "runtime_controller_path": settings["Entrypoint"][0],
        "controller_runtime_identity_method": "complete_target_bytes_plus_observed_immutable_image_root_and_exact_successful_invocation",
        "runtime_controller_same_executable_proven": True, "runtime_controller_byte_rehash_performed": False,
        "runtime_originals_retention_method": "read_only_fixed_owner_return_frame_observation",
        "controller_source_identity": source_identity, "controller_source_coherent": True,
        "controller_invocation_digest": _digest({"entrypoint": settings["Entrypoint"], "argv": settings["Cmd"]}, "invocation"),
        "runtime_configuration_digest": _digest(config, "runtime-config"),
        "runtime_image_metadata_digest": _digest(metadata, "runtime-image-metadata"),
        "runtime_controller_uid": before["uid"], "runtime_controller_gid": before["gid"],
        "runtime_readonly_root": before["readonly_root"], "host_mounts_affecting_controller": False,
        "image_volumes_affecting_controller": False,
        "archive_ancestor_metadata_complete": controller.ancestor_metadata_complete,
        "runtime_controller_traversal_confirmed": True,
        "cleanup": {"bind": True, "bind_sandbox": True, "inspection": dict(inspection.cleanup_evidence),
            "runtime_sandbox": True, "runtime": cleanup, "runtime_backend_controls":
            all(row["control_reaped_and_pipes_closed"] is True for row in measurement["backend_controls"]),
            "runtime_observer_restored": True, "bridge_and_controller_attachments_ephemeral": True,
            "remaining_phase_containers": 0},
        "cleanup_evidence_digest": _digest({"inspection": dict(inspection.cleanup_evidence), "runtime": cleanup,
            "backend_controls": measurement["backend_controls"], "runtime_controls": measurement["controls"]}, "cleanup")}


def _authenticate_owned(value, expected_type, registry, role):
    if type(value) is not expected_type:
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, role + "_original_type_required")
    record = registry.get(value.receipt_id)
    if (record is None or record["object"] is not value or type(value.issuing_pid) is not int
            or value.issuing_pid != os.getpid() or value.owner_identity != OWNER_ID
            or type(value._signature) is not str or not hmac.compare_digest(value._signature, _sign(value))
            or _canonical(_payload(value)) != record["canonical"]
            or value.evidence_digest != _evidence_digest(value, role)):
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, role + "_live_identity_process_signature_required")
    return record


def validate_runtime_attachment(attachment, pinned_receipt, bind_attachment, bind_sd, bind_sr,
        inspection, runtime_descriptor, runtime_receipt, runtime_sd, runtime_sr):
    record = _authenticate_owned(attachment, RuntimeProviderAttachment, _ATTACHMENTS, "runtime-attachment")
    objects = (pinned_receipt, bind_attachment, bind_sd, bind_sr, inspection,
        runtime_descriptor, runtime_receipt, runtime_sd, runtime_sr)
    if any(actual is not original for actual, original in zip(objects, record["upstreams"])):
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "attachment_exact_original_upstreams_required")
    if (attachment.phase_id != PHASE_ID or attachment.schema_version != SCHEMA_VERSION + ":runtime_attachment"
            or attachment.status != COMPLETE or any(getattr(attachment, key) is not False for key in _FALSE_CLAIMS)
            or attachment.exact_provider_proven is not False
            or attachment.evidence_json != _canonical(_runtime_evidence(objects, record["measurement"]))):
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "complete_runtime_attachment_relation_required")
    return attachment


def validate_pinned_java_exact_provider(receipt, pinned_receipt, bind_attachment, bind_sd, bind_sr,
        inspection, runtime_descriptor, runtime_receipt, runtime_sd, runtime_sr, attachment):
    record = _authenticate_owned(receipt, PinnedJavaExactProviderReceipt, _LIVE, "exact-provider")
    objects = (pinned_receipt, bind_attachment, bind_sd, bind_sr, inspection,
        runtime_descriptor, runtime_receipt, runtime_sd, runtime_sr, attachment)
    if any(actual is not original for actual, original in zip(objects, record["upstreams"])):
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "provider_exact_original_graph_required")
    attempt = _ATTEMPTS.get(receipt.proof_context_identity)
    if (attempt is None or attempt["pid"] != os.getpid() or attempt["receipt"] is not receipt):
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "provider_fresh_owner_attempt_required")
    validate_runtime_attachment(attachment, *objects[:9])
    if (receipt.phase_id != PHASE_ID or receipt.schema_version != SCHEMA_VERSION or receipt.status != COMPLETE
            or receipt.requirement_profile != REQUIREMENT.java_profile_id
            or receipt.requirement_schema != REQUIREMENT.java_schema_version
            or receipt.exact_provider_proven is not True
            or any(getattr(receipt, key) is not False for key in _FALSE_CLAIMS)):
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "provider_proof_only_semantics_required")
    evidence = {**json.loads(attachment.evidence_json), "runtime_bridge_evidence_fingerprint": attachment.fingerprint,
        "runtime_attachment_receipt_id": attachment.receipt_id, "runtime_attachment_evidence_digest": attachment.evidence_digest}
    if receipt.evidence_json != _canonical(evidence):
        raise PinnedProviderBlocked(RUNTIME_MISMATCH, "provider_complete_canonical_graph_required")
    return receipt


def _effects(controls):
    return {"docker_control_calls": len(controls), "version_calls": sum(r["command"] == "version" for r in controls),
        "container_create_attempts": sum(r["command"] == "create" for r in controls),
        "container_start_attempts": sum(r["command"] == "start" for r in controls),
        "exact_image_inspect_calls": sum(r["command"] == "image" for r in controls),
        "controls_reaped_and_pipes_closed": all(r["control_reaped_and_pipes_closed"] is True for r in controls)}


def issue_pinned_java_exact_provider():
    """One fresh graph, exactly one runtime component, one final proof root."""
    context = secrets.token_hex(32)
    attempt = {"pid": os.getpid(), "receipt": None}
    _ATTEMPTS[context] = attempt
    report = {"phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION,
        "requirement_profile": REQUIREMENT.java_profile_id, "requirement_schema": REQUIREMENT.java_schema_version,
        "owner_identity": OWNER_ID, "proof_context_identity": context, "status": UNRESOLVED,
        "reason": "proof_not_completed", "exact_provider_proven": False,
        **dict.fromkeys(_FALSE_CLAIMS, False), "report_only": True,
        "fresh_pinned1b_invocations": 0, "fresh_java1c_invocations": 0,
        "operational_effect_counts_outside_frozen_infrastructure": dict.fromkeys(_ZERO_EFFECTS, 0),
        "remaining_phase_containers": None, "cleanup_verified": False}
    binding = attachment = receipt = jd = jr = sd = sr = None
    backend_controls, snapshot = [], None
    try:
        if sys.getprofile() is not None:
            raise PinnedProviderBlocked(UNRESOLVED, "runtime_observer_profile_already_owned")
        report["fresh_pinned1b_invocations"] = 1
        binding = pinned.issue_pinned_backend_target_binding()
        objects = _pinned_objects(binding)
        report["pinned1b_report"] = binding.as_dict()
        if binding.status != pinned.COMPLETE:
            raise PinnedProviderBlocked(binding.status, binding.reason)
        _authenticate_pinned(objects)
        if objects[0].receipt_id in _ORIGINS:
            raise PinnedProviderBlocked(BACKEND_MISMATCH, "previous_provider_attempt_pinned1b_replay")
        _ORIGINS[objects[0].receipt_id] = context
        prefix, endpoint = _fixed_route()
        pre = _measure_backend(prefix, endpoint, backend_controls)
        report["runtime_backend_pre"] = list(pre)
        report["fresh_java1c_invocations"] = 1
        snapshot = _runtime_snapshot()
        jd, jr, runtime_report = snapshot["result"]
        observed = snapshot["verify"][0]
        sd, sr = observed["sd"], observed["sr"]
        report["java1c_report"] = deepcopy(runtime_report)
        post = _measure_backend(prefix, endpoint, backend_controls)
        report["runtime_backend_post"] = list(post)
        if jd is None or jr is None:
            status = CLEANUP_FAILURE if runtime_report["status"] == runtime.CLEANUP_FAILURE else RUNTIME_MISMATCH
            raise PinnedProviderBlocked(status, "fresh_java1c_failed:" + runtime_report["reason"])
        if len(snapshot["invoke"]) != 1 or observed["result"] is not snapshot["result"]:
            raise PinnedProviderBlocked(RUNTIME_MISMATCH, "original_runtime_invocation_observation_required")
        runtime_origin = ("runtime_original", id(jr))
        if runtime_origin in _ORIGINS:
            raise PinnedProviderBlocked(RUNTIME_MISMATCH, "previous_provider_attempt_runtime_replay")
        _ORIGINS[runtime_origin] = context
        invoked = snapshot["invoke"][0]
        measurement = json.loads(_canonical({"pre": list(pre), "post": list(post), "prefix": list(prefix),
            "runtime_prefix": list(observed["prefix"]), "invoke_prefix": list(invoked["prefix"]),
            "configuration": json.loads(invoked["inspected"].stdout), "metadata": observed["metadata"],
            "facts": observed["facts"], "runtime_report": runtime_report,
            "controls": snapshot["controls"], "backend_controls": backend_controls}))
        upstreams = (*objects, jd, jr, sd, sr)
        evidence = _runtime_evidence(upstreams, measurement)
        unsigned = RuntimeProviderAttachment(OWNER_ID, context, secrets.token_hex(32), os.getpid(),
            _canonical(evidence), "")
        unsigned = replace(unsigned, evidence_digest=_evidence_digest(unsigned, "runtime-attachment"))
        attachment = replace(unsigned, _signature=_sign(unsigned))
        _ATTACHMENTS[attachment.receipt_id] = {"object": attachment, "upstreams": upstreams,
            "measurement": measurement, "canonical": _canonical(_payload(attachment))}
        validate_runtime_attachment(attachment, *upstreams)
        evidence = {**evidence, "runtime_bridge_evidence_fingerprint": attachment.fingerprint,
            "runtime_attachment_receipt_id": attachment.receipt_id,
            "runtime_attachment_evidence_digest": attachment.evidence_digest}
        unsigned = PinnedJavaExactProviderReceipt(REQUIREMENT.java_profile_id, REQUIREMENT.java_schema_version,
            OWNER_ID, context, secrets.token_hex(32), os.getpid(), _canonical(evidence), "")
        unsigned = replace(unsigned, evidence_digest=_evidence_digest(unsigned, "exact-provider"))
        receipt = replace(unsigned, _signature=_sign(unsigned))
        _LIVE[receipt.receipt_id] = {"object": receipt, "upstreams": (*upstreams, attachment),
            "canonical": _canonical(_payload(receipt))}
        attempt["receipt"] = receipt
        validate_pinned_java_exact_provider(receipt, *upstreams, attachment)
        report.update(status=COMPLETE, reason="exact_immutable_provider_graph_authenticated",
            exact_provider_proven=True, proof_receipt=receipt.as_dict(), runtime_attachment=attachment.as_dict(),
            provider_proof_receipt_id=receipt.receipt_id, provider_proof_fingerprint=receipt.fingerprint,
            remaining_phase_containers=0, cleanup_verified=True, **evidence)
    except PinnedProviderBlocked as error:
        report.update(status=error.status, reason=error.reason)
        receipt = None
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError) as error:
        report.update(status=UNRESOLVED, reason="provider_graph_unresolved:" + str(error)[:300])
        receipt = None
    report["runtime_backend_effects"] = _effects(backend_controls)
    if snapshot is not None:
        report["runtime_docker_controls"] = snapshot["controls"]
        report["java1c_and_own_sandbox_effects"] = _effects(snapshot["controls"])
        report["operational_effect_counts_by_owner"] = {
            scope: _effects([row for row in snapshot["controls"] if row["scope"] == scope])
            for scope in ("JAVA1C_controls", "JAVA1C_fixed_controller", "JAVA1C_SANDBOX2_infrastructure")}
        runtime_report = report.get("java1c_report", {})
        report["operational_effect_counts_by_owner"]["JAVA1C_fixed_controller"].update(
            frozen_Java_compilations=runtime_report.get("compile_count"),
            frozen_JVM_probe_executions=runtime_report.get("jvm_fixture_count"),
            controller_executions=sum(row["command"] == "start" and row["scope"] == "JAVA1C_fixed_controller"
                for row in snapshot["controls"]))
        sandbox_report = runtime_report.get("live_sandbox2", {})
        report["operational_effect_counts_by_owner"]["JAVA1C_SANDBOX2_infrastructure"].update(
            frozen_java_version_probes=sandbox_report.get("java_version_count"),
            frozen_javac_version_probes=sandbox_report.get("javac_version_count"),
            frozen_Java_compilations=sandbox_report.get("compile_count"),
            frozen_JVM_probe_executions=sandbox_report.get("jvm_fixture_count"))
        report["operational_effect_counts_by_owner"]["runtime_backend_bracket"] = _effects(backend_controls)
        report["operational_effect_counts_by_owner"]["new_attachments"] = {
            "container_creations": 0, "controller_executions": 0, "runtime_controller_byte_rehashes": 0}
        if binding is not None:
            bound = report.get("pinned1b_report", {})
            for role in ("bind_pre_effects", "bind_post_effects", "bind_sandbox2_infrastructure_effects"):
                report["operational_effect_counts_by_owner"][role] = bound.get(role, {})
            report["operational_effect_counts_by_owner"]["PINNED1A"] = bound.get(
                "target_inspection_report", {}).get("operational_effect_counts", {})
    report["stop_boundary"] = "Provider proof only; no SYNTH authorization, lifecycle, lease, executor or Apply."
    return ExactProviderOutcome(report["status"], report["reason"], receipt, binding,
        jd, jr, sd, sr, attachment, report)


def _outcome_objects(outcome):
    return (*_pinned_objects(outcome.pinned_binding), outcome.runtime_descriptor, outcome.runtime_receipt,
        outcome.sandbox_descriptor, outcome.sandbox_receipt, outcome.attachment)


def negative_authentication_matrix(outcome):
    """Pure, reversible live controls. No new owner or infrastructure issuance."""
    values = _outcome_objects(outcome)
    receipt = outcome.receipt
    validate_pinned_java_exact_provider(receipt, *values)
    results = {}

    def rejected(candidate=receipt, objects=values):
        try:
            validate_pinned_java_exact_provider(candidate, *objects)
        except (PinnedProviderBlocked, ValueError, TypeError, AttributeError):
            return True
        return False

    for name, value in (("copy", copy(receipt)), ("deepcopy", deepcopy(receipt)),
            ("dataclasses_replace", replace(receipt)), ("JSON", receipt.as_dict()),
            ("JSON_reconstruction", PinnedJavaExactProviderReceipt(**{key: getattr(receipt, key)
                for key in ("requirement_profile", "requirement_schema", "owner_identity", "proof_context_identity",
                    "receipt_id", "issuing_pid", "evidence_json", "evidence_digest")})),
            ("wrapper", SimpleNamespace(**receipt.as_dict()))):
        results[name] = rejected(value)
    class Subclass(PinnedJavaExactProviderReceipt):
        pass
    results["subclass"] = rejected(Subclass(**{key: getattr(receipt, key) for key in
        ("requirement_profile", "requirement_schema", "owner_identity", "proof_context_identity",
            "receipt_id", "issuing_pid", "evidence_json", "evidence_digest")}))
    with patch.object(os, "getpid", return_value=os.getpid() + 1):
        results["wrong_process"] = rejected()
    for index, role in enumerate(("pinned1b", "BIND_attachment", "BIND_sandbox_descriptor", "BIND_sandbox_receipt",
            "inspection", "JAVA1C_descriptor", "JAVA1C_receipt", "JAVA1C_sandbox_descriptor",
            "JAVA1C_sandbox_receipt", "runtime_attachment")):
        for copier, label in ((copy, "copy"), (deepcopy, "deepcopy")):
            swapped = list(values)
            swapped[index] = copier(values[index])
            results[role + "_" + label] = rejected(objects=tuple(swapped))
        swapped = list(values)
        swapped[index] = values[index].as_dict()
        results[role + "_report_JSON"] = rejected(objects=tuple(swapped))
    for key, changed in {"_signature": "0" * 64, "evidence_digest": "0" * 64,
            "issuing_pid": -1, "owner_identity": "caller-alias", "requirement_profile": "caller-alias",
            "exact_provider_proven": False, **dict.fromkeys(_FALSE_CLAIMS, True)}.items():
        original = getattr(receipt, key)
        try:
            object.__setattr__(receipt, key, changed)
            results["final_" + key] = rejected()
        finally:
            object.__setattr__(receipt, key, original)
    evidence = json.loads(receipt.evidence_json)
    for key in evidence:
        original = receipt.evidence_json
        try:
            changed = {**evidence, key: None}
            object.__setattr__(receipt, "evidence_json", _canonical(changed))
            results["graph_" + key] = rejected()
        finally:
            object.__setattr__(receipt, "evidence_json", original)
    validate_pinned_java_exact_provider(receipt, *values)
    return results
