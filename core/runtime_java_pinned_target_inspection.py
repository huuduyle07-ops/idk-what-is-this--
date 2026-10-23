"""RUNTIME.JAVA.PINNED.1A: exact stopped-target inspection evidence only.

Only inspect_target() has operational effects. It takes no caller target, never
enumerates images and never starts a container. Receipts authenticate target
inspection only, without backend/runtime linkage, lifecycle or authority.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import subprocess
import tempfile
from threading import Event, Thread
from time import monotonic

from core import candidate_runtime_sandbox as sandbox
from core import sandbox_backend_binding as original_binding
from core import sandboxed_java_toolchain_discovery as original
from core import sandboxed_java_positive_probe as java1c_source
from core.runtime_java_pinned_requirement import REQUIREMENT
from core.runtime_java_pinned_target_archive import ArchiveInspectionError, ArchiveInspectionResult, ExecutableMeasurement, inspect_archive

PHASE_ID = "RUNTIME.JAVA.PINNED.1A"
SCHEMA_VERSION = "runtime_java_pinned_target_inspection_1a_v1"
OWNER_ID = "core.runtime_java_pinned_target_inspection"
COMPLETE = "RUNTIME_JAVA_PINNED_1A_COMPLETE"
IMAGE = REQUIREMENT.image_identity
ABSENT = "PINNED_PROVIDER_ABSENT"
METADATA_MISMATCH = "PINNED_PROVIDER_METADATA_MISMATCH"
INSPECTION_INCOMPLETE = "PINNED_PROVIDER_INSPECTION_INCOMPLETE"
TOOLCHAIN_MISMATCH = "PINNED_TOOLCHAIN_MISMATCH"
CONTROLLER_MISMATCH = "PINNED_CONTROLLER_MISMATCH"
CLEANUP_FAILURE = "PINNED_CLEANUP_FAILURE"
UNRESOLVED = "PINNED_PROOF_UNRESOLVED"
_DOMAIN = b"CATTUS:RUNTIME.JAVA.PINNED.1A:target-inspection:v1\x00"
_SECRET = secrets.token_bytes(32)
_LIVE = {}
_EXPORT_CLEANUP_KEYS = {"export_child_reaped", "export_pipes_closed", "deadline_supervisor_stopped", "stderr_reader_stopped"}
_CLEANUP_KEYS = _EXPORT_CLEANUP_KEYS | {"control_children_reaped_and_pipes_closed", "stopped_container_removed",
    "known_container_absence_verified", "temporary_profile_removed", "temporary_workspace_removed", "remaining_phase_containers"}
_NEGATIVE_CODES = {ABSENT, METADATA_MISMATCH, INSPECTION_INCOMPLETE, TOOLCHAIN_MISMATCH,
    CONTROLLER_MISMATCH, CLEANUP_FAILURE, UNRESOLVED}
_ZERO_EFFECTS = ("container_starts", "Java", "javac", "controller_workload_executions", "Java_compilations",
    "source_projections", "network", "shell", "host_mounts", "pulls", "builds", "generic_image_inventory_calls",
    "alternative_image_inspections", "runtime_lease_consumption", "reflection_lease_consumption", "BANK", "EXECUTOR.1R", "Apply", "JAVA.1C_invocations")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return sha256(_DOMAIN + b"evidence\x00" + _canonical(value)).hexdigest()


def _payload(value):
    data = asdict(value)
    data.pop("_signature")
    return data


def _sign(value):
    return hmac.new(_SECRET, _DOMAIN + b"receipt\x00" + _canonical(_payload(value)), "sha256").hexdigest()


@dataclass(frozen=True, slots=True)
class PinnedJavaTargetInspectionReceipt:
    requirement_profile: str
    requirement_schema: str
    owner_identity: str
    proof_context_identity: str
    receipt_id: str
    issuing_pid: int
    image_identity: str
    image_metadata: tuple[tuple[str, str], ...]
    image_metadata_digest: str
    backend_route_identity: str
    backend_server_version: str
    inspection_container_identity: str
    inspection_configuration_digest: str
    inspection_seccomp_policy_sha256: str
    archive: ArchiveInspectionResult
    controller_source_identity: tuple[tuple[str, str], ...]
    cleanup_evidence: tuple[tuple[str, bool | int], ...]
    cleanup_evidence_digest: str
    evidence_digest: str
    export_elapsed_ms: float
    operational_effect_counts: tuple[tuple[str, int], ...]
    _signature: str = field(default="", repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    status: str = field(default=COMPLETE, init=False)
    target_controller_measured: bool = field(default=True, init=False)
    runtime_controller_same_executable_proven: bool = field(default=False, init=False)
    complete_inventory_claimed: bool = field(default=False, init=False)
    complete_local_artifact_discovery_claimed: bool = field(default=False, init=False)
    global_provider_absence_claimed: bool = field(default=False, init=False)
    global_provider_uniqueness_claimed: bool = field(default=False, init=False)
    exact_provider_proven: bool = field(default=False, init=False)
    bind_linkage_proven: bool = field(default=False, init=False)
    java1c_linkage_proven: bool = field(default=False, init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    compatibility_authority: bool = field(default=False, init=False)
    lease_consumption: int = field(default=0, init=False)

    @property
    def fingerprint(self):
        return sha256(_DOMAIN + b"fingerprint\x00" + _canonical(_payload(self))).hexdigest()

    def as_dict(self):
        return {**_payload(self), "inspection_receipt_fingerprint": self.fingerprint, "report_only": True}


@dataclass(frozen=True, slots=True)
class TargetInspectionOutcome:
    status: str
    reason: str
    receipt: PinnedJavaTargetInspectionReceipt | None
    _report: dict = field(repr=False, compare=False)

    def as_dict(self):
        return deepcopy(self._report)


@dataclass(frozen=True, slots=True)
class ExportResult:
    archive: ArchiveInspectionResult | None
    status: str
    reason: str
    elapsed_ms: float
    archive_bytes: int
    cleanup: tuple[tuple[str, bool], ...]


def validate_target_inspection_receipt(receipt):
    """Authenticate the original live object; exported/copy evidence is rejected."""
    if type(receipt) is not PinnedJavaTargetInspectionReceipt:
        raise ValueError("pinned_target_original_typed_receipt_required")
    record = _LIVE.get(receipt.receipt_id)
    if record is None or record[0] is not receipt:
        raise ValueError("pinned_target_live_original_object_required")
    if type(receipt.issuing_pid) is not int or receipt.issuing_pid != os.getpid():
        raise ValueError("pinned_target_issuing_process_required")
    projection = _canonical(_payload(receipt))
    if (type(receipt._signature) is not str
            or not hmac.compare_digest(receipt._signature, _sign(receipt))
            or projection != record[1]
            or receipt.evidence_digest != sha256(_DOMAIN + b"evidence\x00" + record[2]).hexdigest()):
        raise ValueError("pinned_target_signature_or_evidence_changed")
    return receipt


def _issue_receipt(values, evidence):
    """Private issuer, called only after every inspection and cleanup gate."""
    unsigned = PinnedJavaTargetInspectionReceipt(**values, evidence_digest=_digest(evidence))
    cleanup = dict(unsigned.cleanup_evidence)
    archive = unsigned.archive
    if (unsigned.requirement_profile != REQUIREMENT.java_profile_id
            or unsigned.requirement_schema != REQUIREMENT.java_schema_version
            or unsigned.owner_identity != OWNER_ID or unsigned.image_identity != IMAGE
            or type(archive) is not ArchiveInspectionResult
            or any(getattr(archive, name) is not True for name in ("stream_complete", "all_paths_validated", "all_links_validated"))
            or type(archive.archive_bytes) is not int or not 0 < archive.archive_bytes <= REQUIREMENT.inspection_bounds.max_archive_bytes
            or type(archive.archive_entries) is not int or not 0 < archive.archive_entries <= REQUIREMENT.inspection_bounds.max_archive_entries
            or archive.java.normalized_path != REQUIREMENT.java.path or archive.java.sha256 != REQUIREMENT.java.sha256
            or archive.javac.normalized_path != REQUIREMENT.javac.path or archive.javac.sha256 != REQUIREMENT.javac.sha256
            or archive.controller.normalized_path != REQUIREMENT.controller.path
            or archive.toolchain_pair_result != "exact_single_same_directory_pair"
            or PurePosixPath(archive.java.resolved_path).parent != PurePosixPath(archive.javac.resolved_path).parent
            or archive.java.resolved_path == archive.javac.resolved_path
            or set(cleanup) != _CLEANUP_KEYS or len(cleanup) != len(unsigned.cleanup_evidence)
            or any(value is not True for key, value in cleanup.items() if key != "remaining_phase_containers")
            or type(cleanup["remaining_phase_containers"]) is not int or cleanup["remaining_phase_containers"] != 0
            or not 0 <= unsigned.export_elapsed_ms <= REQUIREMENT.inspection_bounds.export_timeout_ms):
        raise ValueError("pinned_target_issuance_gates_incomplete")
    for executable in (archive.java, archive.javac, archive.controller):
        if (type(executable) is not ExecutableMeasurement
                or type(executable.size_bytes) is not int or not 20 <= executable.size_bytes <= REQUIREMENT.inspection_bounds.max_executable_bytes
                or len(executable.sha256) != 64 or any(c not in "0123456789abcdef" for c in executable.sha256)
                or executable.linux_amd64_elf is not True or executable.elf_class != 2 or executable.elf_endianness != 1
                or executable.elf_osabi not in (0, 3) or executable.elf_type not in (2, 3) or executable.elf_machine != 62
                or executable.nonroot_executable is not True or not original._nonroot_can_execute(executable)
                or executable.ancestor_traversal_allowed is not True
                or executable.link_resolution_result != "resolved_within_image_root"
                or len(executable.link_chain) > REQUIREMENT.inspection_bounds.max_link_hops):
            raise ValueError("pinned_target_executable_measurement_incomplete")
    effects = dict(unsigned.operational_effect_counts)
    if (any(type(effects.get(key)) is not int or effects[key] != 0 for key in _ZERO_EFFECTS)
            or effects.get("docker_export_calls") != 1 or effects.get("inspection_containers_created") != 1):
        raise ValueError("pinned_target_forbidden_operational_effect")
    signed = replace(unsigned, _signature=_sign(unsigned))
    _LIVE[signed.receipt_id] = (signed, _canonical(_payload(signed)), _canonical(evidence))
    return validate_target_inspection_receipt(signed)


def _new_report(context):
    counts = dict.fromkeys(("docker_control_calls", "docker_export_calls", "inspection_containers_created", *_ZERO_EFFECTS), 0)
    return {"phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION,
        "requirement_profile": REQUIREMENT.java_profile_id, "requirement_schema": REQUIREMENT.java_schema_version,
        "inspection_owner_identity": OWNER_ID, "proof_context_identity": context,
        "target_image_identity": IMAGE, "target_presence_result": "not_measured",
        "image_metadata_result": "not_measured", "backend_route_identity": None, "backend_server_version": None,
        "inspection_receipt_id": None, "inspection_receipt_fingerprint": None,
        "export_timeout_ms": REQUIREMENT.inspection_bounds.export_timeout_ms, "export_elapsed_ms": None,
        "archive_bytes": 0, "archive_entries": None, "archive_inspection_result": None,
        "controller_runtime_identity_proven": False, "complete_inventory_claimed": False,
        "complete_local_artifact_discovery_claimed": False, "global_provider_absence_claimed": False,
        "global_provider_uniqueness_claimed": False, "exact_provider_proven": False,
        "bind_linkage_proven": False, "java1c_invoked": False, "runtime_proof_issued": False,
        "runtime_authority": False, "operational_effect_counts": counts,
        "control_children_reaped_and_pipes_closed": True, "cleanup": {}, "receipt_authentication": False,
        "report_only": True, "backend_measurement_semantics": "original_local_route_and_linux_Server.Version_only",
        "daemon_continuity_proven": False, "aba_resistance_proven": False,
        "inspection_seccomp_role": "frozen_SANDBOX.1_stopped_inspection_policy; no runtime_SANDBOX.2_verification_claim"}


def _completed(capture):
    return capture.status == "sandbox_completed" and capture.termination_within_deadline is True


def _control(prefix, command, report):
    # No generic control interface is public. Every call is constructed here.
    verb = command[0]
    if verb not in {"version", "image", "create", "inspect", "rm"}:
        raise ValueError("pinned_target_control_verb_forbidden")
    if verb == "image" and tuple(command) != ("image", "inspect", IMAGE, "--format", "{{json .}}"):
        raise ValueError("pinned_target_exact_image_inspect_only")
    report["operational_effect_counts"]["docker_control_calls"] += 1
    try:
        capture = sandbox._bounded_process((*prefix, *command), timeout_ms=8000,
            stdout_limit=65536, stderr_limit=8192)
    except (OSError, subprocess.SubprocessError):
        report["control_children_reaped_and_pipes_closed"] = False
        raise
    # Frozen capture closes both pipes and waits before returning these states;
    # control_failure means reader/reap cleanup cannot be claimed.
    if capture.status not in {"sandbox_completed", "sandbox_timeout", "sandbox_output_limit_exceeded"} or type(capture.exit_code) is not int:
        report["control_children_reaped_and_pipes_closed"] = False
    return capture


def _fixed_route():
    return original_binding._fixed_route()


def _make_workspace():
    return tempfile.TemporaryDirectory(prefix="runtime-java-pinned1a-")


def _write_profile(directory):
    path = Path(directory) / "inspection-seccomp.json"
    content = sandbox._json(sandbox._SECCOMP).encode()
    path.write_bytes(content)
    if path.read_bytes() != content:
        raise ValueError("pinned_target_inspection_policy_changed")
    return path


def _remove_workspace(workspace):
    try:
        workspace.cleanup()
        return not Path(workspace.name).exists()
    except OSError:
        return False


class _CountedPipe:
    def __init__(self, stream):
        self.stream, self.byte_count = stream, 0

    def read(self, size=-1):
        if type(size) is not int or size < 0:
            raise ValueError("pinned_target_unbounded_export_read")
        block = self.stream.read(size)
        self.byte_count += len(block)
        return block


def _export_target(prefix, name):
    """One bounded streamed export; discard archive, no extraction or start."""
    begin = monotonic()
    deadline = begin + REQUIREMENT.inspection_bounds.export_timeout_ms / 1000
    stopped, expired, overflow = Event(), Event(), Event()
    stderr_bytes = bytearray()
    errors = []
    process = reader = supervisor = pipe = None
    archive, status, reason = None, INSPECTION_INCOMPLETE, "export_not_completed"
    cleanup = dict.fromkeys(("export_child_reaped", "export_pipes_closed",
        "deadline_supervisor_stopped", "stderr_reader_stopped"), True)
    elapsed = 0.0
    try:
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR") if key in os.environ}
        process = subprocess.Popen((*prefix, "export", name), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        pipe = _CountedPipe(process.stdout)

        def kill():
            try:
                if process.poll() is None:
                    process.kill()
            except OSError:
                errors.append("export_kill_failed")

        def supervise():
            while not stopped.wait(.02):
                if monotonic() >= deadline:
                    expired.set()
                    kill()
                    return

        def read_stderr():
            try:
                while True:
                    block = process.stderr.read(256)
                    if not block:
                        return
                    remaining = 8192 - len(stderr_bytes)
                    stderr_bytes.extend(block[:remaining])
                    if len(block) > remaining:
                        overflow.set()
                        kill()
                        return
            except OSError:
                errors.append("export_stderr_read_failed")

        supervisor = Thread(target=supervise, daemon=True)
        reader = Thread(target=read_stderr, daemon=True)
        supervisor.start()
        reader.start()
        archive = inspect_archive(pipe)
        exit_code = process.wait(timeout=2)
        elapsed = (monotonic() - begin) * 1000
        if expired.is_set() or elapsed > REQUIREMENT.inspection_bounds.export_timeout_ms:
            reason, archive = "export_timeout", None
        elif overflow.is_set():
            reason, archive = "export_stderr_limit", None
        elif exit_code != 0 or errors:
            reason, archive = "export_failed", None
        else:
            status, reason = COMPLETE, "complete_bounded_target_archive_inspected"
    except ArchiveInspectionError as error:
        status, reason = error.code, error.reason
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        reason = "export_inspection_failed:" + type(error).__name__
    finally:
        elapsed = elapsed or (monotonic() - begin) * 1000
        stopped.set()
        if process is not None:
            try:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=2)
            except (OSError, subprocess.SubprocessError):
                cleanup["export_child_reaped"] = False
            for thread, key in ((supervisor, "deadline_supervisor_stopped"), (reader, "stderr_reader_stopped")):
                if thread is not None and thread.ident is not None:
                    thread.join(timeout=2)
                    cleanup[key] = not thread.is_alive()
                elif thread is not None:
                    cleanup[key] = False
            for stream in (process.stdout, process.stderr):
                try:
                    stream.close()
                except OSError:
                    cleanup["export_pipes_closed"] = False
            if errors:
                cleanup["export_pipes_closed"] = False
        if expired.is_set() or elapsed > REQUIREMENT.inspection_bounds.export_timeout_ms:
            status, reason, archive = INSPECTION_INCOMPLETE, "export_timeout", None
        elif overflow.is_set():
            status, reason, archive = INSPECTION_INCOMPLETE, "export_stderr_limit", None
    return ExportResult(archive, status, reason, elapsed, pipe.byte_count if pipe else 0, tuple(cleanup.items()))


def _controller_source_identity():
    content = java1c_source.source().encode()
    return (("phase_id", "RUNTIME.JAVA.1C"), ("identity_kind", "frozen_controller_source_metadata_only"),
        ("source_sha256", sha256(content).hexdigest()), ("source_size_bytes", str(len(content))))


def inspect_target():
    """Inspect exactly the frozen target once; issue evidence after cleanup."""
    context = secrets.token_hex(32)
    report = _new_report(context)
    status, reason = INSPECTION_INCOMPLETE, "inspection_not_completed"
    prefix = name = workspace = archive = None
    metadata = config = None
    container_attempted, container_removed, known_absent = False, True, True
    workspace_removed, export_cleanup = True, {}
    receipt = None
    try:
        prefix, endpoint = _fixed_route()
        version = _control(prefix, ("version", "--format", "{{json .}}"), report)
        if not _completed(version) or version.exit_code != 0:
            raise ValueError("inspection_backend_version_unavailable")
        route, server = original_binding._backend_witness(version.stdout, endpoint)
        report.update(backend_route_identity=route, backend_server_version=server)
        capture = _control(prefix, ("image", "inspect", IMAGE, "--format", "{{json .}}"), report)
        if not _completed(capture) or capture.exit_code != 0:
            absent = (_completed(capture) and capture.exit_code != 0 and not capture.stdout.strip()
                and IMAGE.encode() in capture.stderr and any(marker in capture.stderr.lower()
                    for marker in (b"no such image:", b"no such object:")))
            status = ABSENT if absent else INSPECTION_INCOMPLETE
            report["target_presence_result"] = "exact_target_absent" if absent else "unavailable_or_ambiguous"
            raise ValueError("exact_target_absent" if absent else "exact_image_inspection_unavailable")
        try:
            metadata = json.loads(capture.stdout)
        except (ValueError, TypeError):
            report["target_presence_result"] = "unavailable_or_ambiguous"
            raise ValueError("exact_image_inspection_metadata_unavailable")
        report["target_presence_result"] = "unavailable_or_ambiguous"
        try:
            artifact = original._image_metadata(IMAGE, metadata)
        except (ValueError, TypeError):
            status = METADATA_MISMATCH
            raise ValueError("exact_target_image_metadata_invalid")
        report["target_presence_result"] = "present"
        if artifact.os != "linux" or artifact.architecture != "amd64" or artifact.image_declared_volumes:
            status = METADATA_MISMATCH
            raise ValueError("exact_target_platform_or_declared_volumes_mismatch")
        report["image_metadata_result"] = "exact_linux_amd64_no_declared_volumes"
        workspace = _make_workspace()
        workspace_removed = False
        profile = _write_profile(workspace.name)
        name = "runtime-java-pinned1a-" + secrets.token_hex(16)
        container_attempted, container_removed, known_absent = True, False, False
        command = ("create", "--name", name, "--pull", "never", "--hostname", "runtime-sandbox1",
            "--network", "none", "--read-only", "--user", "65534:65534", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges=true", "--security-opt", "seccomp=" + str(profile),
            "--cgroupns", "private", "--ipc", "none", "--pids-limit", "128", "--memory", "128m",
            "--cpus", "1", "--log-driver", "none", "--tmpfs", "/work:rw,nosuid,nodev,size=32m,mode=1777",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777", "--workdir", "/work",
            "--entrypoint", REQUIREMENT.controller.path, IMAGE, "-I", "-S", "-B", "-c", "raise SystemExit(64)")
        created = _control(prefix, command, report)
        if not _completed(created) or created.exit_code != 0:
            raise ValueError("stopped_inspection_container_create_failed")
        report["operational_effect_counts"]["inspection_containers_created"] = 1
        inspected = _control(prefix, ("inspect", name, "--format", "{{json .}}"), report)
        if not _completed(inspected) or inspected.exit_code != 0:
            raise ValueError("stopped_inspection_configuration_unavailable")
        config = json.loads(inspected.stdout)
        if (not original._stopped_configuration_safe(config, IMAGE)
                or config.get("Id") != created.stdout.decode().strip()
                or config["Config"].get("Image") != IMAGE
                or config["State"].get("Pid") != 0 or config["State"].get("Status") != "created"):
            status = METADATA_MISMATCH
            raise ValueError("stopped_inspection_configuration_mismatch")
        report["inspection_configuration_digest"] = _digest(config)
        report["operational_effect_counts"]["docker_export_calls"] = 1
        exported = _export_target(prefix, name)
        export_cleanup = dict(exported.cleanup)
        status, reason, archive = exported.status, exported.reason, exported.archive
        report.update(export_elapsed_ms=exported.elapsed_ms, archive_bytes=exported.archive_bytes)
        if archive is not None:
            report.update(archive_entries=archive.archive_entries, archive_inspection_result=asdict(archive))
        if status != COMPLETE or archive is None:
            if status == COMPLETE:
                status, reason = INSPECTION_INCOMPLETE, "export_missing_complete_archive"
            archive = None
        elif (set(export_cleanup) != _EXPORT_CLEANUP_KEYS or exported.archive_bytes != archive.archive_bytes
                or not 0 <= exported.elapsed_ms <= REQUIREMENT.inspection_bounds.export_timeout_ms):
            status, reason, archive = INSPECTION_INCOMPLETE, "export_measurement_incomplete_or_out_of_bounds", None
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        reason = str(error)[:300]
        if status == COMPLETE:
            status = UNRESOLVED
    finally:
        if container_attempted:
            try:
                removed = _control(prefix, ("rm", "--force", "--volumes", name), report)
                absent = _control(prefix, ("inspect", name, "--format", "{{.State.Running}}"), report)
                container_removed = (_completed(removed) and (removed.exit_code == 0 or any(marker in removed.stderr.lower()
                    for marker in (b"no such object", b"no such container"))))
                known_absent = (_completed(absent) and absent.exit_code != 0 and any(marker in absent.stderr.lower()
                    for marker in (b"no such object", b"no such container")))
            except (OSError, ValueError, subprocess.SubprocessError):
                container_removed = known_absent = False
        if workspace is not None:
            workspace_removed = _remove_workspace(workspace)
    cleanup = {**export_cleanup, "control_children_reaped_and_pipes_closed": report["control_children_reaped_and_pipes_closed"],
        "stopped_container_removed": container_removed, "known_container_absence_verified": known_absent,
        "temporary_profile_removed": workspace_removed, "temporary_workspace_removed": workspace_removed,
        "remaining_phase_containers": 0 if known_absent else None}
    report["cleanup"] = cleanup
    if (any(value is not True for key, value in cleanup.items() if key != "remaining_phase_containers")
            or (report["operational_effect_counts"]["docker_export_calls"] == 1 and set(export_cleanup) != _EXPORT_CLEANUP_KEYS)):
        status, reason, archive = CLEANUP_FAILURE, "inspection_cleanup_not_verified", None
    if status not in _NEGATIVE_CODES | {COMPLETE}:
        status, reason, archive = UNRESOLVED, "unsupported_target_inspection_outcome", None
    if status == COMPLETE and archive is not None:
        try:
            values = {"requirement_profile": REQUIREMENT.java_profile_id, "requirement_schema": REQUIREMENT.java_schema_version,
                "owner_identity": OWNER_ID, "proof_context_identity": context, "receipt_id": secrets.token_hex(32),
                "issuing_pid": os.getpid(), "image_identity": IMAGE,
                "image_metadata": (("Id", metadata["Id"]), ("Os", metadata["Os"]), ("Architecture", metadata["Architecture"])),
                "image_metadata_digest": _digest(metadata), "backend_route_identity": report["backend_route_identity"],
                "backend_server_version": report["backend_server_version"], "inspection_container_identity": config["Id"],
                "inspection_configuration_digest": _digest(config),
                "inspection_seccomp_policy_sha256": sha256(sandbox._json(sandbox._SECCOMP).encode()).hexdigest(),
                "archive": archive, "controller_source_identity": _controller_source_identity(),
                "cleanup_evidence": tuple(cleanup.items()), "cleanup_evidence_digest": _digest(cleanup),
                "export_elapsed_ms": report["export_elapsed_ms"],
                "operational_effect_counts": tuple(report["operational_effect_counts"].items())}
            evidence = {"phase_id": PHASE_ID, "schema_version": SCHEMA_VERSION, "measurements": values,
                "raw_image_metadata": metadata, "raw_inspection_configuration": config}
            # asdict recursion is intentional: immutable measured records only.
            evidence["measurements"] = {**values, "archive": asdict(archive)}
            receipt = _issue_receipt(values, evidence)
            report.update(inspection_receipt_id=receipt.receipt_id, inspection_receipt_fingerprint=receipt.fingerprint,
                receipt_authentication=True, inspection_receipt=receipt.as_dict())
        except (ValueError, TypeError, AttributeError) as error:
            status, reason, receipt = UNRESOLVED, "receipt_issuance_failed:" + str(error)[:200], None
    report.update(status=status, reason=reason)
    return TargetInspectionOutcome(status, reason, receipt, report)
