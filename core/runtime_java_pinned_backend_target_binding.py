"""RUNTIME.JAVA.PINNED.1B: one authenticated backend-to-target evidence edge.

The only operational entry point obtains fresh evidence through the two frozen
public owners. Validation is pure, retains their exact original objects, and
grants no runtime, compatibility, lifecycle, or execution authority. Route and
Server.Version equality does not identify a daemon or establish continuity.
"""
from copy import copy, deepcopy
from dataclasses import asdict, dataclass, field, fields, replace
from hashlib import sha256
import hmac
import json
import os
import secrets
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from core import candidate_runtime_sandbox as sandbox
from core import sandbox_backend_binding as backend
from core import thread_compatible_runtime_sandbox as sandbox2
from core import runtime_java_pinned_target_inspection as target
from core.runtime_java_pinned_requirement import REQUIREMENT

PHASE_ID = "RUNTIME.JAVA.PINNED.1B"
SCHEMA_VERSION = "runtime_java_pinned_backend_target_binding_1b_v1"
OWNER_ID = "core.runtime_java_pinned_backend_target_binding"
COMPLETE = "RUNTIME_JAVA_PINNED_1B_COMPLETE"
MISMATCH = "PINNED_BACKEND_BINDING_MISMATCH"
CLEANUP_FAILURE = "PINNED_CLEANUP_FAILURE"
UNRESOLVED = "PINNED_PROOF_UNRESOLVED"
IMAGE = REQUIREMENT.image_identity
_DOMAIN = b"CATTUS:RUNTIME.JAVA.PINNED.1B:backend-target-binding:v1\x00"
_SECRET = secrets.token_bytes(32)
# Strong references and signed original bytes establish evidence provenance;
# neither registry defines an authorization lifecycle or consumption state.
_LIVE = {}
_ATTEMPTS = {}
_UPSTREAM_ORIGINS = {}
_FALSE_CLAIMS = ("daemon_identity_claimed", "daemon_continuity_claimed",
    "aba_resistance_claimed", "exact_provider_proven", "runtime_controller_identity_proven",
    "java1c_linkage_proven", "java1c_invoked", "runtime_proof_issued",
    "complete_inventory_claimed", "global_provider_absence_claimed",
    "global_provider_uniqueness_claimed", "runtime_authority", "repository_write_authority",
    "apply_authority", "compatibility_authority")
_CLEANUP_KEYS = frozenset(("export_child_reaped", "export_pipes_closed",
    "deadline_supervisor_stopped", "stderr_reader_stopped", "control_children_reaped_and_pipes_closed",
    "stopped_container_removed", "known_container_absence_verified", "temporary_profile_removed",
    "temporary_workspace_removed", "remaining_phase_containers"))
_ZERO_EFFECTS = ("container_starts", "Java", "javac", "controller_workload_executions",
    "Java_compilations", "source_projections", "network", "shell", "host_mounts", "pulls", "builds",
    "generic_image_inventory_calls", "alternative_image_inspections", "runtime_lease_consumption",
    "reflection_lease_consumption", "BANK", "EXECUTOR.1R", "Apply", "JAVA.1C_invocations")


class PinnedBindingBlocked(ValueError):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value, role=b"evidence"):
    return sha256(_DOMAIN + role + b"\x00" + _canonical(value)).hexdigest()


def _payload(value):
    data = asdict(value)
    data.pop("_signature")
    return data


def _evidence_payload(value):
    data = _payload(value)
    data.pop("evidence_digest")
    return data


def _sign(value):
    return hmac.new(_SECRET, _DOMAIN + b"receipt\x00" + _canonical(_payload(value)), "sha256").hexdigest()


@dataclass(frozen=True, slots=True)
class PinnedJavaBackendTargetBindingReceipt:
    requirement_profile: str
    requirement_schema: str
    owner_identity: str
    proof_context_identity: str
    receipt_id: str
    issuing_pid: int
    target_image_identity: str
    canonical_backend_route_identity: str
    canonical_backend_server_version: str
    bind_attachment_id: str
    bind_attachment_fingerprint: str
    bind_semantics_id: str
    bind_bracket_equal: bool
    bind_sandbox_descriptor_fingerprint: str
    bind_sandbox_receipt_fingerprint: str
    bind_sandbox_receipt_evidence_digest: str
    inspection_owner_identity: str
    inspection_proof_context_identity: str
    inspection_receipt_id: str
    inspection_receipt_fingerprint: str
    inspection_evidence_digest: str
    inspection_cleanup_evidence_digest: str
    inspection_image_identity: str
    inspection_backend_route_identity: str
    inspection_backend_server_version: str
    inspection_controller_identity: tuple[tuple[str, str], ...]
    inspection_controller_evidence_digest: str
    inspection_controller_source_identity: tuple[tuple[str, str], ...]
    evidence_digest: str
    _signature: str = field(default="", repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    status: str = field(default=COMPLETE, init=False)
    route_equal: bool = field(default=True, init=False)
    version_equal: bool = field(default=True, init=False)
    image_equal: bool = field(default=True, init=False)
    upstream_authenticated: bool = field(default=True, init=False)
    binding_result: bool = field(default=True, init=False)
    bind_cleanup_verified: bool = field(default=True, init=False)
    bind_sandbox_cleanup_verified: bool = field(default=True, init=False)
    inspection_cleanup_verified: bool = field(default=True, init=False)
    remaining_phase_containers: int = field(default=0, init=False)
    daemon_identity_claimed: bool = field(default=False, init=False)
    daemon_continuity_claimed: bool = field(default=False, init=False)
    aba_resistance_claimed: bool = field(default=False, init=False)
    exact_provider_proven: bool = field(default=False, init=False)
    runtime_controller_identity_proven: bool = field(default=False, init=False)
    java1c_linkage_proven: bool = field(default=False, init=False)
    java1c_invoked: bool = field(default=False, init=False)
    runtime_proof_issued: bool = field(default=False, init=False)
    complete_inventory_claimed: bool = field(default=False, init=False)
    global_provider_absence_claimed: bool = field(default=False, init=False)
    global_provider_uniqueness_claimed: bool = field(default=False, init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    compatibility_authority: bool = field(default=False, init=False)

    @property
    def fingerprint(self):
        return _digest(_payload(self), b"fingerprint")

    def as_dict(self):
        """Report-only projection; neither reconstruction nor copying authenticates."""
        return {**_payload(self), "binding_receipt_fingerprint": self.fingerprint, "report_only": True}


@dataclass(frozen=True, slots=True)
class BackendTargetBindingOutcome:
    status: str
    reason: str
    receipt: PinnedJavaBackendTargetBindingReceipt | None
    bind_attachment: backend.SandboxBackendBindingAttachment | None
    sandbox_descriptor: sandbox2.ThreadCompatibleSandboxDescriptor | None
    sandbox_receipt: sandbox2.ThreadCompatibleSandboxReceipt | None
    inspection_receipt: target.PinnedJavaTargetInspectionReceipt | None
    _report: dict = field(repr=False, compare=False)

    def as_dict(self):
        return deepcopy(self._report)


def _authenticate_upstreams(attachment, descriptor, sandbox_receipt, inspection):
    if (type(attachment) is not backend.SandboxBackendBindingAttachment
            or type(descriptor) is not sandbox2.ThreadCompatibleSandboxDescriptor
            or type(sandbox_receipt) is not sandbox2.ThreadCompatibleSandboxReceipt
            or type(inspection) is not target.PinnedJavaTargetInspectionReceipt):
        raise PinnedBindingBlocked(MISMATCH, "exact_original_upstream_types_required")
    cleanup = dict(inspection.cleanup_evidence)
    if (any(getattr(attachment, key) is not True for key in ("sandbox_cleanup_verified",
            "pre_control_reaped_and_pipes_closed", "post_control_reaped_and_pipes_closed",
            "temporary_workspace_removed"))
            or type(attachment.remaining_phase_containers) is not int or attachment.remaining_phase_containers != 0
            or sandbox_receipt.cleanup_verified is not True
            or len(cleanup) != len(inspection.cleanup_evidence) or set(cleanup) != _CLEANUP_KEYS
            or any(value is not True for key, value in cleanup.items() if key != "remaining_phase_containers")
            or type(cleanup.get("remaining_phase_containers")) is not int or cleanup["remaining_phase_containers"] != 0):
        raise PinnedBindingBlocked(CLEANUP_FAILURE, "all_exact_upstream_cleanup_required")
    try:
        # Owner APIs, rather than copied HMAC logic or report hashes, authenticate.
        backend.validate_sandbox_backend_binding(attachment, descriptor, sandbox_receipt)
        target.validate_target_inspection_receipt(inspection)
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        raise PinnedBindingBlocked(MISMATCH, "upstream_owner_authentication_failed:" + str(error)) from error
    if (attachment.phase_id != "RUNTIME.SANDBOX.BIND.1"
            or attachment.schema_version != "runtime_sandbox_backend_binding_1_v1"
            or attachment.binding_semantics != "original_java1_route_and_server_version_v1"
            or attachment.route_version_bracket_equal is not True
            or attachment.sandbox_policy_sha256 != REQUIREMENT.sandbox_policy_sha256
            or descriptor.seccomp_policy_sha256 != REQUIREMENT.sandbox_policy_sha256
            or sandbox_receipt.seccomp_policy_sha256 != REQUIREMENT.sandbox_policy_sha256
            or any(getattr(attachment, key) is not False for key in ("daemon_instance_identity_available",
                "daemon_continuity_proven", "aba_resistance_proven"))
            or inspection.phase_id != "RUNTIME.JAVA.PINNED.1A"
            or inspection.schema_version != "runtime_java_pinned_target_inspection_1a_v1"
            or inspection.status != target.COMPLETE or inspection.owner_identity != target.OWNER_ID
            or inspection.requirement_profile != REQUIREMENT.java_profile_id
            or inspection.requirement_schema != REQUIREMENT.java_schema_version
            or type(inspection.proof_context_identity) is not str or not inspection.proof_context_identity
            or any(getattr(inspection, key) is not False for key in ("exact_provider_proven",
                "runtime_controller_same_executable_proven", "java1c_linkage_proven", "runtime_authority",
                "complete_inventory_claimed", "global_provider_absence_claimed", "global_provider_uniqueness_claimed"))):
        raise PinnedBindingBlocked(MISMATCH, "exact_upstream_contract_required")
    if not (attachment.image_identity == descriptor.image_identity == sandbox_receipt.image_identity
            == inspection.image_identity == IMAGE):
        raise PinnedBindingBlocked(MISMATCH, "immutable_target_image_identity_mismatch")
    if attachment.canonical_backend_identity != inspection.backend_route_identity:
        raise PinnedBindingBlocked(MISMATCH, "backend_route_identity_mismatch")
    if attachment.canonical_backend_version != inspection.backend_server_version:
        raise PinnedBindingBlocked(MISMATCH, "backend_server_version_mismatch")


def _upstream_values(attachment, descriptor, sandbox_receipt, inspection):
    controller = inspection.archive.controller
    return {"target_image_identity": IMAGE,
        "canonical_backend_route_identity": attachment.canonical_backend_identity,
        "canonical_backend_server_version": attachment.canonical_backend_version,
        "bind_attachment_id": attachment.attachment_id, "bind_attachment_fingerprint": attachment.fingerprint,
        "bind_semantics_id": attachment.binding_semantics, "bind_bracket_equal": attachment.route_version_bracket_equal,
        "bind_sandbox_descriptor_fingerprint": descriptor.fingerprint,
        "bind_sandbox_receipt_fingerprint": sandbox_receipt.fingerprint,
        "bind_sandbox_receipt_evidence_digest": sandbox_receipt.evidence_sha256,
        "inspection_owner_identity": inspection.owner_identity,
        "inspection_proof_context_identity": inspection.proof_context_identity,
        "inspection_receipt_id": inspection.receipt_id, "inspection_receipt_fingerprint": inspection.fingerprint,
        "inspection_evidence_digest": inspection.evidence_digest,
        "inspection_cleanup_evidence_digest": inspection.cleanup_evidence_digest,
        "inspection_image_identity": inspection.image_identity,
        "inspection_backend_route_identity": inspection.backend_route_identity,
        "inspection_backend_server_version": inspection.backend_server_version,
        "inspection_controller_identity": (("normalized_path", controller.normalized_path),
            ("resolved_path", controller.resolved_path), ("sha256", controller.sha256)),
        "inspection_controller_evidence_digest": _digest(asdict(controller), b"measured-controller"),
        "inspection_controller_source_identity": inspection.controller_source_identity}


def _retain_fresh_upstreams(context, attachment, descriptor, sandbox_receipt, inspection):
    """Capture exact results of this attempt's public issuers; no caller aliases."""
    origins = (("bind", attachment.attachment_id), ("inspection", inspection.receipt_id),
        ("inspection_context", inspection.proof_context_identity))
    if context not in _ATTEMPTS or _ATTEMPTS[context][1] is not None:
        raise PinnedBindingBlocked(MISMATCH, "owner_established_fresh_attempt_required")
    if any(key in _UPSTREAM_ORIGINS for key in origins):
        raise PinnedBindingBlocked(MISMATCH, "upstream_evidence_from_previous_binding_attempt")
    upstreams = (attachment, descriptor, sandbox_receipt, inspection)
    _ATTEMPTS[context] = (os.getpid(), upstreams)
    for key in origins:
        _UPSTREAM_ORIGINS[key] = context


def _issue_receipt(context, attachment, descriptor, sandbox_receipt, inspection):
    """Pure private issuer, after fresh public-owner results have been retained."""
    upstreams = (attachment, descriptor, sandbox_receipt, inspection)
    attempt = _ATTEMPTS.get(context)
    if (attempt is None or attempt[0] != os.getpid() or attempt[1] is None
            or any(actual is not original for actual, original in zip(upstreams, attempt[1]))):
        raise PinnedBindingBlocked(MISMATCH, "exact_fresh_attempt_upstreams_required")
    _authenticate_upstreams(*upstreams)
    unsigned = PinnedJavaBackendTargetBindingReceipt(
        requirement_profile=REQUIREMENT.java_profile_id, requirement_schema=REQUIREMENT.java_schema_version,
        owner_identity=OWNER_ID, proof_context_identity=context, receipt_id=secrets.token_hex(32),
        issuing_pid=os.getpid(), **_upstream_values(*upstreams), evidence_digest="")
    unsigned = replace(unsigned, evidence_digest=_digest(_evidence_payload(unsigned)))
    signed = replace(unsigned, _signature=_sign(unsigned))
    _LIVE[signed.receipt_id] = (signed, upstreams, _canonical(_payload(signed)))
    return validate_pinned_backend_target_binding(signed, *upstreams)


def validate_pinned_backend_target_binding(receipt, bind_attachment, sandbox_descriptor,
        sandbox_receipt, inspection_receipt):
    """Pure current-process authentication against every exact upstream original."""
    if type(receipt) is not PinnedJavaBackendTargetBindingReceipt:
        raise PinnedBindingBlocked(MISMATCH, "original_typed_binding_receipt_required")
    record = _LIVE.get(receipt.receipt_id)
    if (record is None or record[0] is not receipt or type(receipt.issuing_pid) is not int
            or receipt.issuing_pid != os.getpid()):
        raise PinnedBindingBlocked(MISMATCH, "binding_live_process_provenance_required")
    if (type(receipt._signature) is not str or not hmac.compare_digest(receipt._signature, _sign(receipt))
            or _canonical(_payload(receipt)) != record[2]
            or receipt.evidence_digest != _digest(_evidence_payload(receipt))):
        raise PinnedBindingBlocked(MISMATCH, "binding_signature_or_canonical_evidence_changed")
    upstreams = (bind_attachment, sandbox_descriptor, sandbox_receipt, inspection_receipt)
    if any(actual is not original for actual, original in zip(upstreams, record[1])):
        raise PinnedBindingBlocked(MISMATCH, "binding_exact_upstream_objects_required")
    attempt = _ATTEMPTS.get(receipt.proof_context_identity)
    if (attempt is None or attempt[0] != os.getpid()
            or any(actual is not original for actual, original in zip(upstreams, attempt[1]))):
        raise PinnedBindingBlocked(MISMATCH, "binding_exact_fresh_attempt_required")
    _authenticate_upstreams(*upstreams)
    if (receipt.phase_id != PHASE_ID or receipt.schema_version != SCHEMA_VERSION
            or receipt.status != COMPLETE or receipt.owner_identity != OWNER_ID
            or receipt.requirement_profile != REQUIREMENT.java_profile_id
            or receipt.requirement_schema != REQUIREMENT.java_schema_version
            or any(getattr(receipt, key) is not False for key in _FALSE_CLAIMS)
            or any(getattr(receipt, key) is not True for key in ("route_equal", "version_equal", "image_equal",
                "upstream_authenticated", "binding_result", "bind_cleanup_verified",
                "bind_sandbox_cleanup_verified", "inspection_cleanup_verified"))
            or type(receipt.remaining_phase_containers) is not int or receipt.remaining_phase_containers != 0
            or any(getattr(receipt, key) != value for key, value in _upstream_values(*upstreams).items())):
        raise PinnedBindingBlocked(MISMATCH, "binding_exact_semantics_and_upstream_identities_required")
    return receipt


def _effects(calls):
    return {"docker_control_calls": len(calls),
        "docker_version_calls": sum(row["command"] == "version" for row in calls),
        "container_create_attempts": sum(row["command"] == "create" for row in calls),
        "containers_created": sum(row["command"] == "create" and row["completed"]
            and row["exit_code"] == 0 for row in calls),
        "container_start_attempts": sum(row["command"] == "start" for row in calls),
        "exact_image_inspect_calls": sum(row["command"] == "image" and row["operation"] == "inspect" for row in calls),
        "generic_image_inventory_calls": sum(row["command"] == "image" and row["operation"] == "ls" for row in calls),
        "docker_export_calls": sum(row["command"] == "export" for row in calls),
        "pulls": sum(row["command"] == "pull" for row in calls),
        "builds": sum(row["command"] == "build" for row in calls)}


def issue_pinned_backend_target_binding():
    """One bounded fresh BIND and one fresh target inspection, with no retries.

    No historical/caller-selected evidence input exists. Frozen owners establish
    their own independent freshness contexts; this owner relates exact results.
    Public replay observation below supplies report accounting, never provenance.
    """
    context = secrets.token_hex(32)
    _ATTEMPTS[context] = (os.getpid(), None)
    report = {"phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION,
        "requirement_profile": REQUIREMENT.java_profile_id, "requirement_schema": REQUIREMENT.java_schema_version,
        "target_image_identity": IMAGE, "binding_owner_identity": OWNER_ID, "proof_context_identity": context,
        "status": UNRESOLVED, "reason": "fresh_upstream_issuance_not_completed", "report_only": True,
        "fresh_bind_invocations": 0, "fresh_target_inspection_invocations": 0,
        "binding_receipt_id": None, "binding_receipt_fingerprint": None,
        "binding_authentication": False, "upstream_reauthentication": False,
        "route_equal": False, "version_equal": False, "image_equal": False,
        "cleanup_verified": False, "remaining_phase_containers": None,
        **dict.fromkeys(_FALSE_CLAIMS, False), "operational_effect_counts": dict.fromkeys(_ZERO_EFFECTS, 0)}
    attachment = descriptor = sandbox_receipt = inspection = receipt = None
    calls, scope, sandbox_reports = [], ["bind_pre"], []
    invoke, replay_sandbox = sandbox._bounded_process, sandbox2.replay

    def observed(argv, **kwargs):
        row = {"scope": scope[0], "command": argv[5] if len(argv) > 5 else "",
            "operation": argv[6] if len(argv) > 6 and argv[5] == "image" else None,
            "completed": False, "exit_code": None, "control_reaped_and_pipes_closed": False}
        calls.append(row)
        capture = invoke(argv, **kwargs)
        row.update(completed=capture.status == "sandbox_completed", exit_code=capture.exit_code,
            control_reaped_and_pipes_closed=capture.status in ("sandbox_completed", "sandbox_timeout",
                "sandbox_output_limit_exceeded"))
        return capture

    def observed_sandbox():
        scope[0] = "bind_sandbox2_infrastructure"
        try:
            live_report = replay_sandbox()
            sandbox_reports.append(deepcopy(live_report))
            return live_report
        finally:
            scope[0] = "bind_post"

    try:
        with patch.object(sandbox, "_bounded_process", observed), patch.object(sandbox2, "replay", observed_sandbox):
            report["fresh_bind_invocations"] = 1
            attachment, descriptor, sandbox_receipt = backend.issue_sandbox_backend_binding()
        backend.validate_sandbox_backend_binding(attachment, descriptor, sandbox_receipt)
        report.update(bind_attachment=attachment.as_dict(), bind_sandbox_descriptor=descriptor.as_dict(),
            bind_sandbox_receipt=sandbox_receipt.as_dict())
        report["fresh_target_inspection_invocations"] = 1
        outcome = target.inspect_target()
        if type(outcome) is not target.TargetInspectionOutcome:
            raise PinnedBindingBlocked(MISMATCH, "original_target_inspection_outcome_required")
        report["target_inspection_report"] = outcome.as_dict()
        inspection = outcome.receipt
        if outcome.status != target.COMPLETE or inspection is None:
            raise PinnedBindingBlocked(outcome.status, outcome.reason)
        _authenticate_upstreams(attachment, descriptor, sandbox_receipt, inspection)
        _retain_fresh_upstreams(context, attachment, descriptor, sandbox_receipt, inspection)
        receipt = _issue_receipt(context, attachment, descriptor, sandbox_receipt, inspection)
        validate_pinned_backend_target_binding(receipt, attachment, descriptor, sandbox_receipt, inspection)
        report.update(status=COMPLETE, reason="fresh_authenticated_backend_to_target_binding_only",
            binding_receipt_id=receipt.receipt_id, binding_receipt_fingerprint=receipt.fingerprint,
            binding_receipt=receipt.as_dict(), binding_authentication=True, upstream_reauthentication=True,
            route_equal=True, version_equal=True, image_equal=True,
            cleanup_verified=True, remaining_phase_containers=0)
    except backend.BindingBlocked as error:
        status = (CLEANUP_FAILURE if error.status == backend.CLEANUP else MISMATCH
            if error.status in (backend.SANDBOX_AUTH, backend.ROUTE_VERSION_CHANGED, backend.ATTACHMENT_AUTH)
            else UNRESOLVED)
        report.update(status=status,
            reason="fresh_bind_failed:" + str(error), bind_status=error.status)
    except PinnedBindingBlocked as error:
        report.update(status=error.status, reason=error.reason)
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        report.update(status=MISMATCH, reason="upstream_evidence_or_binding_failed:" + str(error)[:250])
    except (OSError, subprocess.SubprocessError) as error:
        report.update(status=UNRESOLVED, reason="bounded_upstream_infrastructure_failed:" + str(error)[:250])
    # Failed owner inputs must not masquerade as typed outcome evidence or break
    # report accounting after their authentication has already been rejected.
    if type(attachment) is not backend.SandboxBackendBindingAttachment:
        attachment = None
    if type(descriptor) is not sandbox2.ThreadCompatibleSandboxDescriptor:
        descriptor = None
    if type(sandbox_receipt) is not sandbox2.ThreadCompatibleSandboxReceipt:
        sandbox_receipt = None
    if type(inspection) is not target.PinnedJavaTargetInspectionReceipt:
        inspection = None
    report["bind_docker_control_calls"] = calls
    report["bind_pre_effects"] = _effects([row for row in calls if row["scope"] == "bind_pre"])
    report["bind_post_effects"] = _effects([row for row in calls if row["scope"] == "bind_post"])
    report["bind_sandbox2_infrastructure_effects"] = _effects(
        [row for row in calls if row["scope"] == "bind_sandbox2_infrastructure"])
    if sandbox_reports:
        live_report = sandbox_reports[0]
        report["bind_sandbox2_report"] = live_report
        report["bind_sandbox2_infrastructure_effects"].update(
            java_version_count=live_report.get("java_version_count"),
            javac_version_count=live_report.get("javac_version_count"),
            java_compilations=live_report.get("compile_count"),
            java_fixture_executions=live_report.get("jvm_fixture_count"),
            console_count=live_report.get("console_count"),
            behavioral_execution_count=live_report.get("behavioral_execution_count"))
    if inspection is not None and type(inspection) is target.PinnedJavaTargetInspectionReceipt:
        report["target_inspection_effects"] = dict(inspection.operational_effect_counts)
    elif "target_inspection_report" in report:
        report["target_inspection_effects"] = report["target_inspection_report"].get("operational_effect_counts", {})
    inspection_cleanup = report.get("target_inspection_report", {}).get("cleanup", {})
    sandbox_report = report.get("bind_sandbox2_report", {})
    bind_cleanup = {}
    for label in ("pre", "post"):
        key = label + "_control_reaped_and_pipes_closed"
        rows = [row for row in calls if row["scope"] == "bind_" + label]
        bind_cleanup[key] = (getattr(attachment, key) if attachment is not None
            else len(rows) == 1 and rows[0]["command"] == "version"
                and rows[0]["control_reaped_and_pipes_closed"])
    bind_cleanup.update(
        sandbox_cleanup_verified=(sandbox_receipt.cleanup_verified is True if sandbox_receipt is not None
            else sandbox_report.get("cleanup_verified") is True),
        temporary_workspace_removed=(attachment.temporary_workspace_removed if attachment is not None
            else sandbox_report.get("temporary_workspace_removed") is True),
        remaining_phase_containers=(attachment.remaining_phase_containers if attachment is not None
            else sandbox_report.get("phase_container_count_after_teardown")))
    report["bind_cleanup"] = bind_cleanup
    report["cleanup"] = {
        "bind_cleanup_verified": (all(bind_cleanup[key] is True for key in ("sandbox_cleanup_verified",
                "pre_control_reaped_and_pipes_closed", "post_control_reaped_and_pipes_closed",
                "temporary_workspace_removed"))
            and type(bind_cleanup["remaining_phase_containers"]) is int
            and bind_cleanup["remaining_phase_containers"] == 0),
        "bind_sandbox_cleanup_verified": bind_cleanup["sandbox_cleanup_verified"],
        "inspection_cleanup_verified": (set(inspection_cleanup) == _CLEANUP_KEYS
            and all(value is True for key, value in inspection_cleanup.items() if key != "remaining_phase_containers")
            and type(inspection_cleanup.get("remaining_phase_containers")) is int
            and inspection_cleanup["remaining_phase_containers"] == 0),
        "bind_remaining_phase_containers": (attachment.remaining_phase_containers if attachment is not None
            else sandbox_report.get("phase_container_count_after_teardown")),
        "inspection_remaining_phase_containers": inspection_cleanup.get("remaining_phase_containers")}
    known_remaining = [report["cleanup"][key] for key in
        ("bind_remaining_phase_containers", "inspection_remaining_phase_containers")]
    if all(type(count) is int for count in known_remaining):
        report["remaining_phase_containers"] = sum(known_remaining)
    report["cleanup_verified"] = all(report["cleanup"][key] is True for key in
        ("bind_cleanup_verified", "bind_sandbox_cleanup_verified", "inspection_cleanup_verified"))
    report["operational_effect_scope"] = "outside_frozen_BIND_SANDBOX_infrastructure_probes"
    report["frozen_infrastructure_probe_note"] = (
        "BIND SANDBOX.2 controller/containment and Java/javac version probes are frozen infrastructure effects; "
        "target inspection starts no container and performs no Java, javac or controller workload execution.")
    if report["status"] != COMPLETE:
        if receipt is not None:
            _LIVE.pop(receipt.receipt_id, None)
        receipt = None
    return BackendTargetBindingOutcome(report["status"], report["reason"], receipt,
        attachment, descriptor, sandbox_receipt, inspection, report)


def negative_authentication_matrix(outcome):
    """Pure copy/substitution/tamper controls, restoring originals before return."""
    if type(outcome) is not BackendTargetBindingOutcome or outcome.receipt is None:
        raise PinnedBindingBlocked(MISMATCH, "successful_live_binding_outcome_required")
    receipt = outcome.receipt
    upstreams = (outcome.bind_attachment, outcome.sandbox_descriptor,
        outcome.sandbox_receipt, outcome.inspection_receipt)
    results = {}

    def rejects(name, candidate=receipt, supplied=upstreams):
        try:
            validate_pinned_backend_target_binding(candidate, *supplied)
        except (ValueError, TypeError, AttributeError, KeyError):
            results[name] = True
        else:
            results[name] = False

    for name, candidate in (("copy", copy(receipt)), ("deepcopy", deepcopy(receipt)),
            ("dataclasses_replace", replace(receipt)), ("report_only_json", receipt.as_dict()),
            ("wrapper", SimpleNamespace(**receipt.as_dict())), ("caller_string_alias", receipt.fingerprint)):
        rejects(name, candidate)
    data = json.loads(json.dumps(receipt.as_dict()))
    init_values = {f.name: getattr(receipt, f.name) for f in fields(receipt) if f.init}
    rejects("json_reconstruction", PinnedJavaBackendTargetBindingReceipt(**{
        f.name: data[f.name] for f in fields(receipt) if f.init and f.name != "_signature"}))
    class Subclass(PinnedJavaBackendTargetBindingReceipt):
        pass
    rejects("subclass", Subclass(**init_values))
    for index, label in enumerate(("different_bind_attachment", "different_bind_sandbox_descriptor",
            "same_bind_descriptor_different_receipt", "different_inspection_receipt")):
        supplied = list(upstreams)
        supplied[index] = deepcopy(supplied[index])
        rejects(label, supplied=tuple(supplied))
    rejects("report_only_bind_json", supplied=(upstreams[0].as_dict(), *upstreams[1:]))
    rejects("report_only_pinned_json", supplied=(*upstreams[:3], upstreams[3].as_dict()))
    rejects("bind_caller_string_alias", supplied=(upstreams[0].fingerprint, *upstreams[1:]))
    rejects("inspection_caller_string_alias", supplied=(*upstreams[:3], upstreams[3].fingerprint))
    rejects("different_bind_sandbox_receipt", supplied=(*upstreams[:2],
        replace(upstreams[2], evidence_sha256="0" * 64), upstreams[3]))
    rejects("same_inspection_fields_copied_object", supplied=(*upstreams[:3], deepcopy(upstreams[3])))
    rejects("old_java1_discovery_substitution", supplied=(*upstreams[:3], SimpleNamespace(
        phase_id="RUNTIME.JAVA.1", schema_version="runtime_java_1_v1", image_identity=IMAGE)))
    with patch.object(os, "getpid", return_value=receipt.issuing_pid + 1):
        rejects("wrong_process")

    def tamper(name, obj, key, value):
        original = getattr(obj, key)
        try:
            object.__setattr__(obj, key, value)
            rejects(name)
        finally:
            object.__setattr__(obj, key, original)

    for key in ("requirement_profile", "requirement_schema", "target_image_identity",
            "canonical_backend_route_identity", "canonical_backend_server_version",
            "bind_attachment_fingerprint", "bind_sandbox_descriptor_fingerprint",
            "bind_sandbox_receipt_fingerprint", "bind_sandbox_receipt_evidence_digest",
            "inspection_receipt_fingerprint", "inspection_evidence_digest", "inspection_cleanup_evidence_digest",
            "inspection_proof_context_identity", "evidence_digest"):
        tamper("changed_" + key, receipt, key, "changed")
    tamper("wrong_hmac", receipt, "_signature", "0" * 64)
    for key in _FALSE_CLAIMS:
        tamper("forbidden_" + key, receipt, key, True)
    for label, key in (("bind_route_mismatch", "canonical_backend_identity"),
            ("bind_version_mismatch", "canonical_backend_version"), ("image_mismatch", "image_identity"),
            ("changed_bind_descriptor_fingerprint", "sandbox_descriptor_fingerprint"),
            ("changed_bind_receipt_fingerprint", "sandbox_receipt_fingerprint"),
            ("changed_bind_evidence_digest", "sandbox_receipt_evidence_sha256")):
        tamper(label, upstreams[0], key, "changed")
    for key in ("proof_context_identity", "receipt_id", "evidence_digest", "cleanup_evidence_digest"):
        tamper("changed_inspection_" + key, upstreams[3], key, "changed")
    tamper("wrong_inspection_hmac", upstreams[3], "_signature", "0" * 64)
    tamper("bind_cleanup_failure", upstreams[0], "sandbox_cleanup_verified", False)
    tamper("bind_sandbox_cleanup_failure", upstreams[2], "cleanup_verified", False)
    cleanup = tuple((key, 1 if key == "remaining_phase_containers" else value)
        for key, value in upstreams[3].cleanup_evidence)
    tamper("inspection_cleanup_failure", upstreams[3], "cleanup_evidence", cleanup)
    validate_pinned_backend_target_binding(receipt, *upstreams)
    return results
