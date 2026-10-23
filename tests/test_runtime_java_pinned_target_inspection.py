"""Mocked target controls and live-object authentication; no real Docker runs."""
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, asdict, fields, replace
from hashlib import sha256
import inspect
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import runtime_java_pinned_target_inspection as owner
    from core import runtime_java_pinned_target_archive as archive_owner

_REAL_EXPORT_TARGET = owner._export_target


@pytest.fixture(autouse=True)
def effects():
    with no_runtime_effects(strict=True) as evidence:
        with patch("threading.Thread.start", side_effect=evidence.deny("thread_start")):
            yield
    assert evidence.denied_attempts == {}


def _capture(stdout=b"", stderr=b"", **changes):
    values = dict(status="sandbox_completed", exit_code=0, stdout=stdout,
        stderr=stderr, deadline_triggered=False, termination_verified=True,
        termination_within_deadline=True, measured_termination_ms=0.1)
    values.update(changes)
    return owner.sandbox._Capture(**values)


def _measurement(path, digest, *, resolved=None):
    return archive_owner.ExecutableMeasurement(path, resolved or path, digest, 64,
        2, 1, 0, 3, 62, True, 0o755, 0, 0, True, True, True,
        (("/", True),), (), "resolved_within_image_root")


def _archive_result():
    requirement = owner.REQUIREMENT
    return archive_owner.ArchiveInspectionResult(10240, 12,
        _measurement(requirement.java.path, requirement.java.sha256),
        _measurement(requirement.javac.path, requirement.javac.sha256),
        _measurement(requirement.controller.path, "c" * 64,
            resolved="/usr/local/bin/python3.12"), "exact_single_same_directory_pair")


def _metadata():
    return {"Id": owner.IMAGE, "Os": "linux", "Architecture": "amd64",
        "Size": 12345, "RepoDigests": [], "Config": {"Env": [], "Volumes": {}}}


def _configuration(container_id):
    return {"Id": container_id, "Image": owner.IMAGE, "Mounts": [],
        "State": {"Running": False, "Pid": 0, "Status": "created"},
        "Config": {"Image": owner.IMAGE, "User": "65534:65534", "WorkingDir": "/work",
            "Entrypoint": [owner.REQUIREMENT.controller.path],
            "Cmd": ["-I", "-S", "-B", "-c", "raise SystemExit(64)"]},
        "HostConfig": {"Privileged": False, "NetworkMode": "none", "PidMode": "",
            "IpcMode": "none", "CgroupnsMode": "private", "ReadonlyRootfs": True,
            "Binds": [], "Mounts": [], "CapDrop": ["ALL"], "CapAdd": [],
            "LogConfig": {"Type": "none"}, "PidsLimit": 128, "Memory": 134217728,
            "NanoCpus": 1000000000, "Tmpfs": {"/work": "rw,nosuid,nodev,size=32m,mode=1777",
                "/tmp": "rw,nosuid,nodev,noexec,size=16m,mode=1777"},
            "SecurityOpt": ["no-new-privileges=true",
                "seccomp=" + owner.sandbox._json(owner.sandbox._SECCOMP)]}}


@pytest.fixture
def control(monkeypatch):
    """Fabricated successful measurements test owner gates, never image bytes."""
    endpoint = "npipe:////./pipe/dockerDesktopLinuxEngine"
    state = SimpleNamespace(prefix=("fixed-docker.exe", "--config", "absent", "--host", endpoint),
        endpoint=endpoint, container_id="d" * 64, metadata=_metadata(),
        configuration=_configuration("d" * 64), commands=[], order=[], captures={},
        export=_archive_result(), export_status=owner.COMPLETE, export_reason="fixture_control",
        export_elapsed=5.0, workspace_removed=True,
        export_cleanup={key: True for key in ("export_child_reaped", "export_pipes_closed",
            "deadline_supervisor_stopped", "stderr_reader_stopped")})

    def measured(argv, **kwargs):
        assert argv[:len(state.prefix)] == state.prefix
        command = argv[len(state.prefix):]
        state.commands.append((command, kwargs))
        role = command[0]
        if command[:2] == ("image", "inspect"):
            assert command == ("image", "inspect", owner.IMAGE, "--format", "{{json .}}")
            role = "image"
            default = _capture(json.dumps(state.metadata).encode())
        elif role == "version":
            default = _capture(b'{"Server":{"Os":"linux","Version":" Exact.01 "}}')
        elif role == "create":
            assert command.count(owner.IMAGE) == 1
            state.name = command[command.index("--name") + 1]
            default = _capture(state.container_id.encode())
        elif role == "inspect" and command[-1] == "{{json .}}":
            assert command[1] == state.name
            role = "configuration"
            default = _capture(json.dumps(state.configuration).encode())
        elif role == "inspect":
            assert command == ("inspect", state.name, "--format", "{{.State.Running}}")
            role = "absence"
            default = _capture(exit_code=1, stderr=b"No such object: fixture-stopped")
        elif role == "rm":
            assert command == ("rm", "--force", "--volumes", state.name)
            default = _capture()
        else:
            pytest.fail("Unexpected Docker control: " + repr(command))
        state.order.append(role)
        return state.captures.get(role, default)

    def exported(prefix, name):
        assert prefix == state.prefix and name == state.name
        state.order.append("export")
        return owner.ExportResult(state.export, state.export_status, state.export_reason,
            state.export_elapsed, state.export.archive_bytes if state.export else 0,
            tuple(state.export_cleanup.items()))

    def remove_workspace(workspace):
        state.order.append("workspace_removed")
        return state.workspace_removed

    monkeypatch.setattr(owner, "_fixed_route", lambda: (state.prefix, endpoint))
    monkeypatch.setattr(owner.sandbox, "_bounded_process", measured)
    monkeypatch.setattr(owner, "_make_workspace", lambda: SimpleNamespace(name="C:/fixture/pinned1a"))
    monkeypatch.setattr(owner, "_write_profile", lambda directory: Path(directory) / "seccomp.json")
    monkeypatch.setattr(owner, "_remove_workspace", remove_workspace)
    monkeypatch.setattr(owner, "_export_target", exported)
    with patch.dict(owner._LIVE, {}, clear=True):
        yield state


@pytest.fixture
def issued(control):
    outcome = owner.inspect_target()
    assert outcome.status == owner.COMPLETE
    assert outcome.receipt is not None
    return outcome.receipt


def test_one_exact_stopped_create_and_export_with_cleanup_before_issuance(control, monkeypatch):
    original_issue = owner._issue_receipt

    def issue_after_cleanup(values, evidence):
        assert control.order == ["version", "image", "create", "configuration", "export", "rm", "absence", "workspace_removed"]
        return original_issue(values, evidence)

    monkeypatch.setattr(owner, "_issue_receipt", issue_after_cleanup)
    outcome = owner.inspect_target()
    receipt, report = outcome.receipt, outcome.as_dict()
    assert outcome.status == owner.COMPLETE
    assert owner.validate_target_inspection_receipt(receipt) is receipt
    commands = [command for command, _ in control.commands]
    assert [command[0] for command in commands] == ["version", "image", "create", "inspect", "rm", "inspect"]
    assert not any(command[0] in {"start", "exec", "run", "pull", "build", "ps"} for command in commands)
    created = commands[2]
    for option, value in (("--pull", "never"), ("--network", "none"), ("--user", "65534:65534"),
            ("--cap-drop", "ALL"), ("--cgroupns", "private"), ("--ipc", "none"),
            ("--pids-limit", "128"), ("--memory", "128m"), ("--cpus", "1")):
        assert created[created.index(option) + 1] == value
    assert "--read-only" in created
    assert "--mount" not in created and "--volume" not in created
    counts = report["operational_effect_counts"]
    assert {name: counts[name] for name in ("docker_control_calls", "docker_export_calls", "inspection_containers_created")} == {
        "docker_control_calls": 6, "docker_export_calls": 1, "inspection_containers_created": 1}
    assert all(type(value) is int and value == 0 for name, value in counts.items()
        if name not in {"docker_control_calls", "docker_export_calls", "inspection_containers_created"})
    assert all(kwargs == {"timeout_ms": 8000, "stdout_limit": 65536, "stderr_limit": 8192}
        for _, kwargs in control.commands)
    assert report["cleanup"]["remaining_phase_containers"] == 0
    assert all(value is True for key, value in report["cleanup"].items() if key != "remaining_phase_containers")


def test_public_owner_has_no_target_endpoint_or_caller_witness_argument(control):
    assert not inspect.signature(owner.inspect_target).parameters
    for value in (owner.IMAGE, "mutable:tag", "sha256:" + "a" * 64, {}, None):
        with pytest.raises(TypeError):
            owner.inspect_target(value)
    assert control.commands == []


@pytest.mark.parametrize("command", [("image", "ls"), ("start", "fixture-stopped"),
    ("exec", "fixture-stopped", "java"), ("image", "inspect", "mutable:tag", "--format", "{{json .}}"),
    ("image", "inspect", "sha256:" + "0" * 64, "--format", "{{json .}}")])
def test_internal_controls_reject_inventory_start_and_alternative_targets_before_transport(control, command):
    report = owner._new_report("fabricated_context")
    with pytest.raises(ValueError):
        owner._control(control.prefix, command, report)
    assert control.commands == []
    assert report["operational_effect_counts"]["docker_control_calls"] == 0


@pytest.mark.parametrize("capture", [_capture(status="sandbox_timeout", exit_code=-9),
    _capture(exit_code=1), _capture(stdout=b'{"Client":{"Version":"1"}}'),
    _capture(stdout=b'{"Server":{"Os":"windows","Version":"1"}}')])
def test_unavailable_backend_measurement_stops_before_target_inspection(control, capture):
    control.captures["version"] = capture
    outcome = owner.inspect_target()
    assert outcome.status == owner.INSPECTION_INCOMPLETE and outcome.receipt is None
    assert control.order == ["version"]
    assert outcome.as_dict()["target_presence_result"] == "not_measured"


@pytest.mark.parametrize("capture,status", [
    (_capture(exit_code=1, stderr=b"No such image: " + owner.IMAGE.encode()), owner.ABSENT),
    (_capture(exit_code=1, stderr=b"No such object: " + owner.IMAGE.encode()), owner.ABSENT),
    (_capture(exit_code=1, stderr=b"No such image: mutable:tag"), owner.INSPECTION_INCOMPLETE),
    (_capture(exit_code=1, stderr=b"daemon unavailable " + owner.IMAGE.encode()), owner.INSPECTION_INCOMPLETE),
    (_capture(exit_code=1, stdout=b"ambiguous", stderr=b"No such image: " + owner.IMAGE.encode()), owner.INSPECTION_INCOMPLETE),
    (_capture(status="sandbox_timeout", exit_code=-9), owner.INSPECTION_INCOMPLETE),
    (_capture(exit_code=1, termination_within_deadline=False), owner.INSPECTION_INCOMPLETE),
])
def test_conclusive_exact_absence_is_distinct_from_unavailable_inspection(control, capture, status):
    control.captures["image"] = capture
    outcome = owner.inspect_target()
    assert outcome.status == status and outcome.receipt is None
    assert control.order == ["version", "image"]
    report = outcome.as_dict()
    assert report["global_provider_absence_claimed"] is False
    assert "NO_SUITABLE_LOCAL_JAVA_ARTIFACT" not in outcome.reason
    assert owner._LIVE == {}


@pytest.mark.parametrize("field,value", [("Id", "mutable:tag"), ("Id", "sha256:" + "b" * 64),
    ("Os", "windows"), ("Architecture", "arm64"), ("Size", True)])
def test_image_identity_and_platform_metadata_fail_before_create(control, field, value):
    control.metadata[field] = value
    outcome = owner.inspect_target()
    assert outcome.status == owner.METADATA_MISMATCH and outcome.receipt is None
    assert control.order == ["version", "image"]


def test_declared_volumes_fail_before_workspace_or_create(control):
    control.metadata["Config"]["Volumes"] = {"/data": {}}
    assert owner.inspect_target().status == owner.METADATA_MISMATCH
    assert control.order == ["version", "image"]


@pytest.mark.parametrize("raw", [b"not-json", b'{"Id":', b"\xff"])
def test_unparseable_image_inspection_is_incomplete_without_absence_inference(control, raw):
    control.captures["image"] = _capture(stdout=raw)
    outcome = owner.inspect_target()
    assert outcome.status == owner.INSPECTION_INCOMPLETE and outcome.receipt is None
    assert control.order == ["version", "image"]
    assert outcome.as_dict()["target_presence_result"] == "unavailable_or_ambiguous"
    assert outcome.as_dict()["global_provider_absence_claimed"] is False


@pytest.mark.parametrize("path,value", [("Image", "sha256:" + "a" * 64), ("Id", "wrong-container"),
    ("Config.Image", "mutable:tag"), ("State.Running", True), ("State.Pid", 1),
    ("State.Status", "exited"), ("HostConfig.NetworkMode", "bridge"),
    ("HostConfig.Privileged", True), ("HostConfig.ReadonlyRootfs", False),
    ("HostConfig.Binds", ["C:/host:/work"]), ("HostConfig.CapAdd", ["SYS_ADMIN"]),
    ("HostConfig.PidsLimit", 256), ("Config.User", "0:0")])
def test_independent_stopped_configuration_mismatch_blocks_export_and_still_cleans(control, path, value):
    target = control.configuration
    parts = path.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value
    outcome = owner.inspect_target()
    assert outcome.status == owner.METADATA_MISMATCH and outcome.receipt is None
    assert "export" not in control.order
    assert control.order[-3:] == ["rm", "absence", "workspace_removed"]


@pytest.mark.parametrize("status", [owner.INSPECTION_INCOMPLETE, owner.TOOLCHAIN_MISMATCH,
    owner.CONTROLLER_MISMATCH, owner.UNRESOLVED])
def test_incomplete_or_mismatched_export_never_partially_accepts_measured_binaries(control, status):
    control.export_status = status
    control.export_reason = "fabricated_negative_control"
    outcome = owner.inspect_target()
    assert outcome.status == status and outcome.receipt is None
    assert owner._LIVE == {}
    assert control.order[-3:] == ["rm", "absence", "workspace_removed"]


@pytest.mark.parametrize("status", ["PINNED_BACKEND_BINDING_MISMATCH", "PINNED_RUNTIME_EVIDENCE_MISMATCH"])
def test_unattempted_backend_or_runtime_outcomes_cannot_be_emitted_by_target_phase(control, status):
    control.export_status = status
    outcome = owner.inspect_target()
    assert outcome.status == owner.UNRESOLVED and outcome.receipt is None
    assert owner._LIVE == {}


@pytest.mark.parametrize("role", ["java", "javac", "controller"])
def test_wrong_exact_executable_identity_cannot_issue_receipt(control, role):
    measured = getattr(control.export, role)
    change = {"sha256": "0" * 64} if role != "controller" else {"normalized_path": "/usr/bin/python"}
    control.export = replace(control.export, **{role: replace(measured, **change)})
    outcome = owner.inspect_target()
    assert outcome.status != owner.COMPLETE and outcome.receipt is None
    assert owner._LIVE == {}


@pytest.mark.parametrize("field,value", [("stream_complete", False), ("all_paths_validated", False),
    ("all_links_validated", False), ("toolchain_pair_result", "ambiguous"), ("archive_entries", 250001),
    ("archive_bytes", 2147483649)])
def test_malformed_complete_export_control_cannot_bypass_archive_commitments(control, field, value):
    control.export = replace(control.export, **{field: value})
    outcome = owner.inspect_target()
    assert outcome.status != owner.COMPLETE and outcome.receipt is None


@pytest.mark.parametrize("failure", ["export_child_reaped", "export_pipes_closed", "deadline_supervisor_stopped",
    "stderr_reader_stopped", "rm", "absence", "workspace", "missing_export_cleanup", "control"])
@pytest.mark.parametrize("prior_status", [owner.COMPLETE, owner.TOOLCHAIN_MISMATCH])
def test_cleanup_failure_takes_precedence_over_positive_and_mismatch_evidence(control, failure, prior_status):
    control.export_status = prior_status
    if failure in control.export_cleanup:
        control.export_cleanup[failure] = False
    elif failure == "missing_export_cleanup":
        control.export_cleanup = {}
    elif failure == "workspace":
        control.workspace_removed = False
    elif failure == "control":
        control.captures["rm"] = _capture(status="sandbox_control_failure", exit_code=None)
    else:
        control.captures[failure] = _capture(exit_code=1, stderr=b"daemon unavailable")
    outcome = owner.inspect_target()
    assert outcome.status == owner.CLEANUP_FAILURE and outcome.receipt is None
    assert owner._LIVE == {}


def test_live_receipt_measures_controller_without_freezing_runtime_identity(issued):
    assert owner.validate_target_inspection_receipt(issued) is issued
    assert issued.requirement_profile == owner.REQUIREMENT.java_profile_id
    assert issued.requirement_schema == owner.REQUIREMENT.java_schema_version
    assert issued.owner_identity == owner.OWNER_ID
    assert issued.image_identity == owner.IMAGE
    assert issued.backend_route_identity == "local-docker:npipe:////./pipe/dockerDesktopLinuxEngine"
    assert issued.backend_server_version == " Exact.01 "
    assert issued.archive.controller.sha256 == "c" * 64
    assert issued.archive.controller.resolved_path == "/usr/local/bin/python3.12"
    assert issued.target_controller_measured is True
    assert owner.REQUIREMENT.controller.pinned_sha256 is None
    assert issued.runtime_controller_same_executable_proven is False
    assert dict(issued.controller_source_identity)["source_sha256"] == sha256(owner.java1c_source.source().encode()).hexdigest()
    assert issued.issuing_pid == owner.os.getpid()
    assert len(issued.receipt_id) == len(issued.proof_context_identity) == len(issued.fingerprint) == 64
    assert owner._SECRET != owner.sandbox._SECRET
    assert owner._SECRET != owner.original_binding._SECRET
    with pytest.raises(FrozenInstanceError):
        issued.backend_server_version = "changed"


def test_receipt_never_claims_inventory_provider_proof_authority_or_lifecycle(issued):
    projection = issued.as_dict()
    for name in ("runtime_controller_same_executable_proven", "complete_inventory_claimed",
            "complete_local_artifact_discovery_claimed", "global_provider_absence_claimed",
            "global_provider_uniqueness_claimed", "exact_provider_proven", "bind_linkage_proven",
            "java1c_linkage_proven", "runtime_authority", "repository_write_authority",
            "apply_authority", "compatibility_authority"):
        assert projection[name] is False
        with pytest.raises((ValueError, TypeError)):
            replace(issued, **{name: True})
    assert issued.lease_consumption == 0
    assert not {"complete_inventory", "complete_local_artifact_discovery", "consume", "invalidate",
        "lease_id", "lifecycle_state"} & set(projection)
    assert not hasattr(issued, "consume")
    assert projection["report_only"] is True


@pytest.mark.parametrize("kind", ["copy", "deepcopy", "replace", "json", "reconstructed", "wrapper", "subclass"])
def test_copies_json_and_foreign_objects_cannot_recreate_process_local_authenticity(issued, kind):
    if kind == "copy": candidate = copy(issued)
    elif kind == "deepcopy": candidate = deepcopy(issued)
    elif kind == "replace": candidate = replace(issued)
    elif kind == "json": candidate = json.loads(json.dumps(issued.as_dict()))
    elif kind == "wrapper": candidate = SimpleNamespace(**issued.as_dict())
    else:
        cls = owner.PinnedJavaTargetInspectionReceipt
        if kind == "subclass":
            class Subclass(cls): pass
            cls = Subclass
        candidate = cls(**{field.name: getattr(issued, field.name) for field in fields(issued) if field.init})
    with pytest.raises(ValueError):
        owner.validate_target_inspection_receipt(candidate)
    assert owner.validate_target_inspection_receipt(issued) is issued


@pytest.mark.parametrize("field,value", [("_signature", "0" * 64), ("receipt_id", "0" * 64),
    ("image_identity", "sha256:" + "a" * 64), ("backend_route_identity", "caller-alias"),
    ("backend_server_version", "Exact.01"), ("inspection_configuration_digest", "0" * 64),
    ("image_metadata_digest", "0" * 64), ("cleanup_evidence_digest", "0" * 64),
    ("cleanup_evidence", ()), ("evidence_digest", "0" * 64),
    ("proof_context_identity", "0" * 64), ("owner_identity", "another-owner")])
def test_changed_bound_identity_cleanup_digest_or_signature_is_rejected(issued, field, value):
    object.__setattr__(issued, field, value)
    with pytest.raises(ValueError):
        owner.validate_target_inspection_receipt(issued)


@pytest.mark.parametrize("role", ["java", "javac", "controller"])
def test_nested_executable_tampering_is_rejected(issued, role):
    measured = getattr(issued.archive, role)
    object.__setattr__(measured, "sha256", "0" * 64)
    with pytest.raises(ValueError):
        owner.validate_target_inspection_receipt(issued)


def test_wrong_process_or_missing_registry_rejects_matching_signed_receipt(issued, monkeypatch):
    pid = owner.os.getpid()
    monkeypatch.setattr(owner.os, "getpid", lambda: pid + 1)
    with pytest.raises(ValueError):
        owner.validate_target_inspection_receipt(issued)
    monkeypatch.setattr(owner.os, "getpid", lambda: pid)
    owner._LIVE.clear()
    with pytest.raises(ValueError):
        owner.validate_target_inspection_receipt(issued)


def test_each_attempt_has_fresh_receipt_and_context_with_no_consumption(control):
    first = owner.inspect_target().receipt
    second = owner.inspect_target().receipt
    assert first.receipt_id != second.receipt_id and first.proof_context_identity != second.proof_context_identity
    assert owner.validate_target_inspection_receipt(first) is first
    assert owner.validate_target_inspection_receipt(second) is second


def test_report_projection_is_detached_from_original_receipt(control):
    outcome = owner.inspect_target()
    report = outcome.as_dict()
    report["inspection_receipt"]["archive"]["java"]["sha256"] = "0" * 64
    report["cleanup"].clear()
    assert owner.validate_target_inspection_receipt(outcome.receipt) is outcome.receipt
    assert outcome.as_dict()["cleanup"]


def test_export_timeout_reaps_child_and_closes_pipes_without_real_threads(control, monkeypatch):
    child = SimpleNamespace(stdout=io.BytesIO(b"fabricated-archive"), stderr=io.BytesIO(),
        returncode=0, killed=False, waits=0)
    child.poll = lambda: child.returncode
    def wait(**kwargs): child.waits += 1; return child.returncode
    def kill(): child.killed = True; child.returncode = -9
    child.wait, child.kill = wait, kill
    calls = []
    def popen(argv, **kwargs): calls.append((argv, kwargs)); return child
    class FakeThread:
        def __init__(self, **kwargs): self.ident = None
        def start(self): self.ident = 1
        def join(self, **kwargs): pass
        def is_alive(self): return False
    ticks = iter((0.0, 31.0))
    monkeypatch.setattr(owner.subprocess, "Popen", popen)
    monkeypatch.setattr(owner, "Thread", FakeThread)
    monkeypatch.setattr(owner, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(owner, "inspect_archive", lambda stream: control.export)
    # The fixture patches the orchestration seam; call the original helper.
    result = _REAL_EXPORT_TARGET(control.prefix, "fixture-stopped")
    assert result.status == owner.INSPECTION_INCOMPLETE and result.archive is None
    assert result.reason == "export_timeout" and result.elapsed_ms == 31000
    assert child.waits == 2 and child.stdout.closed and child.stderr.closed
    assert all(value is True for _, value in result.cleanup)
    assert calls[0][0] == (*control.prefix, "export", "fixture-stopped")
    assert calls[0][1]["shell"] is False
