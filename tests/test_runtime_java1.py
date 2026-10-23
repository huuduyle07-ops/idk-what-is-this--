"""Pure Java capability contract tests, never synthetic runtime evidence.

The local replay alone measures Java/OS effects. This suite denies processes,
network, console, provider calls, repository traversal and writes throughout;
fabricated facts exercise negative predicates without issuing capability.
"""
import base64
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import sha256

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import candidate_runtime_sandbox as sandbox
    from core import sandboxed_java_toolchain as owner
    from core import sandboxed_java_toolchain_discovery as discovery


@pytest.fixture(scope="module", autouse=True)
def deny_entire_focused_suite():
    with no_runtime_effects() as evidence:
        yield evidence
        assert evidence.denied_attempts == {}


def _missing():
    return discovery.LocalJavaDiscovery((), True, True,
        "no_eligible_exact_local_java_toolchain")


def _pair():
    return discovery.LocalJavaToolchainPair(
        "/opt/java/bin/java", "a" * 64, "/opt/java/bin/javac", "b" * 64,
        "/usr/local/bin/python", "c" * 64)


def _capture(status="sandbox_completed", *, stdout=b"", stderr=b"", exit_code=0,
             within_deadline=True):
    return sandbox._Capture(status, exit_code, stdout, stderr, False, True, within_deadline)


def _stage(argv, *, stdout=b"", stderr=b"", exit_code=0, overflow=False):
    return {"argv": list(argv), "exit_code": exit_code, "overflow": overflow,
        "stdout_b64": base64.b64encode(stdout).decode(),
        "stderr_b64": base64.b64encode(stderr).decode()}


def _facts(spec):
    return {
        "environment": dict(sandbox._WORKLOAD_ENVIRONMENT), "uid": 65534,
        "pid_is_one": True, "no_new_privileges": True, "capabilities_zero": True,
        "descendants_contained": True,
        "source_sha256": sha256(owner.JAVA_SOURCE).hexdigest(),
        "source_size_bytes": len(owner.JAVA_SOURCE),
        "javac_binary_sha256": spec.javac_sha256, "java_binary_sha256": spec.java_sha256,
        "class_manifest": [{"path": "JavaSandboxProbe.class", "sha256": "d" * 64,
                            "size_bytes": 400}],
        "stages": {
            "javac_identity": _stage((spec.javac_path, "-version"), stdout=b"javac 17.0.1\n"),
            "java_identity": _stage((spec.java_path, "-version"), stderr=b'openjdk version "17.0.1"\n'),
            "javac": _stage(spec.compile_argv),
            "java": _stage(spec.runtime_argv, stdout=owner.EXPECTED_OUTPUT),
        },
    }


@pytest.fixture
def blocked(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("missing Java artifact attempted a runtime or fallback effect")
    monkeypatch.setattr(sandbox, "_VERIFIED_ADAPTER", None)
    monkeypatch.setattr(discovery, "discover_local_java_artifacts", lambda **kwargs: _missing())
    monkeypatch.setattr(sandbox, "verify_candidate_runtime_sandbox", forbidden)
    monkeypatch.setattr(sandbox, "_bounded_process", forbidden)
    monkeypatch.setattr(owner, "_verify_image_boundary", forbidden)
    monkeypatch.setattr(owner, "_invoke_java", forbidden)
    monkeypatch.setattr(owner.tempfile, "TemporaryDirectory", forbidden)
    return owner.verify_sandboxed_java_toolchain()


@pytest.fixture
def sandbox_blocked(monkeypatch):
    monkeypatch.setattr(sandbox, "_VERIFIED_ADAPTER", None)
    monkeypatch.setattr(sandbox, "discover_local_sandbox_backend", lambda **kwargs:
        sandbox.SandboxBackendObservation("Windows-AMD64", "", "", "", False,
                                        False, "sandbox_backend_unavailable"))
    return sandbox.verify_candidate_runtime_sandbox()


def test_missing_local_artifact_is_authenticated_typed_block_without_any_effect(blocked):
    descriptor, receipt = blocked
    assert receipt.status == owner.UNAVAILABLE
    assert receipt.reason == "no_suitable_local_java_artifact"
    assert receipt.discovery_complete is True
    assert receipt.artifact_inventory == ()
    assert receipt.cleanup_result == "discovery_resources_removed_no_java_workload"
    assert receipt.toolchain_launch_count == receipt.synthetic_java_execution_count == 0
    assert receipt.compile_result == receipt.runtime_result == "not_executed"
    assert receipt.class_output == receipt.image_boundary_outcomes == ()
    assert receipt.bounded_stdout == receipt.bounded_stderr == ""
    assert descriptor.available is descriptor.verified is False
    assert descriptor.javac_available is descriptor.java_runtime_available is False
    assert descriptor.source_projection_supported is descriptor.class_output_projection_supported is False
    assert owner.validate_java_verification_receipt(receipt) is receipt
    assert owner.validate_java_descriptor(descriptor, receipt) is descriptor


def test_infrastructure_capability_never_grants_candidate_or_apply_authority(blocked):
    descriptor, receipt = blocked
    payload = receipt.as_dict()
    assert payload["authority"] == "synthetic_java_infrastructure_measurement_only"
    for name in ("candidate_execution_count", "bank_execution_count", "behavioral_scenario_count",
                 "reflection_count", "console_count", "model_calls", "author_calls",
                 "repository_traversals", "source_mutation", "image_pulls", "installations", "downloads"):
        assert payload[name] == 0
    for record in (descriptor, receipt):
        for name in ("runtime_authority", "repository_write_authority", "apply_authority"):
            assert record.as_dict()[name] is False


def test_reporting_and_semantic_fingerprints_exclude_timing_and_authentication(blocked):
    first_descriptor, first_receipt = blocked
    measured = {"total_seconds": 999999.0}
    second_descriptor, second_receipt = owner.verify_sandboxed_java_toolchain(timings=measured)
    assert first_descriptor.fingerprint == second_descriptor.fingerprint
    assert first_receipt.fingerprint == second_receipt.fingerprint
    assert set(measured) == set(owner.TIMING_FIELDS)
    assert all(value >= 0 for value in measured.values())
    assert all(measured[name] == 0 for name in owner.TIMING_FIELDS
        if name not in ("artifact_discovery_seconds", "total_seconds"))
    for record in (first_descriptor, first_receipt):
        report = record.as_dict()
        assert "_signature" not in report
        assert not any("seconds" in key for key in report)
        assert not ({"container_id", "temp_path", "pid", "created_at"} & set(report))


@pytest.mark.parametrize("reported", (False, True))
def test_forged_descriptor_and_report_json_cannot_create_capability(blocked, reported):
    descriptor, receipt = blocked
    forged = replace(descriptor, available=True, verified=True, sandbox_compatibility=True,
        javac_available=True, java_runtime_available=True,
        source_projection_supported=True, class_output_projection_supported=True)
    supplied = forged.as_dict() if reported else forged
    assert owner.java_toolchain_satisfies_executor_runtime(supplied, None) is False
    with pytest.raises(owner.SandboxedJavaToolchainError) as error:
        owner.validate_java_descriptor(supplied, receipt)
    assert error.value.code == "java_descriptor_unauthenticated"
    assert error.value.java_execution_count == error.value.bank_execution_count == 0


def test_exported_receipt_json_is_report_only(blocked):
    descriptor, receipt = blocked
    with pytest.raises(owner.SandboxedJavaToolchainError) as error:
        owner.validate_java_verification_receipt(receipt.as_dict())
    assert error.value.code == "java_receipt_unauthenticated"
    with pytest.raises(owner.SandboxedJavaToolchainError):
        owner.validate_java_descriptor(descriptor, receipt.as_dict())


@pytest.mark.parametrize("value", (b"forged-version", float("nan"), float("inf")))
def test_malformed_exact_record_payloads_fail_with_typed_authentication_errors(blocked, value):
    descriptor, receipt = blocked
    forged_receipt = replace(receipt, compiler_version=value)
    forged_descriptor = replace(descriptor, compiler_version=value)
    with pytest.raises(owner.SandboxedJavaToolchainError) as error:
        owner.validate_java_verification_receipt(forged_receipt)
    assert error.value.code == "java_receipt_unauthenticated"
    with pytest.raises(owner.SandboxedJavaToolchainError) as error:
        owner.validate_java_descriptor(forged_descriptor, receipt)
    assert error.value.code == "java_descriptor_unauthenticated"
    assert owner.java_toolchain_satisfies_executor_runtime(forged_descriptor, None) is False


@pytest.mark.parametrize("change", (
    {"status": owner.COMPLETE, "reason": "forged"},
    {"cleanup_result": "all_phase_resources_removed"},
    {"source_sha256": "0" * 64},
    {"java_artifact_identity": "sha256:" + "a" * 64},
    {"runtime_invocation_identity": "a" * 64},
))
def test_receipt_tampering_cannot_reuse_authentication_or_descriptor_builder(blocked, change):
    _, receipt = blocked
    forged = replace(receipt, **change)
    with pytest.raises(owner.SandboxedJavaToolchainError) as error:
        owner.validate_java_verification_receipt(forged)
    assert error.value.code == "java_receipt_unauthenticated"
    with pytest.raises(owner.SandboxedJavaToolchainError):
        owner._descriptor(forged)


def test_descriptor_requires_exact_authenticated_receipt_pair(blocked, monkeypatch):
    descriptor, _ = blocked
    monkeypatch.setattr(discovery, "discover_local_java_artifacts", lambda **kwargs:
        discovery.LocalJavaDiscovery((), False, True, "different_local_inventory_observation"))
    _, other_receipt = owner.verify_sandboxed_java_toolchain()
    with pytest.raises(owner.SandboxedJavaToolchainError) as error:
        owner.validate_java_descriptor(descriptor, other_receipt)
    assert error.value.code == "java_descriptor_unauthenticated"


def test_supplied_sandbox_receipt_is_authenticated_before_discovery(sandbox_blocked, monkeypatch):
    descriptor, receipt = sandbox_blocked
    def forbidden(**kwargs):
        raise AssertionError("forged sandbox binding reached artifact discovery")
    monkeypatch.setattr(discovery, "discover_local_java_artifacts", forbidden)
    with pytest.raises(sandbox.CandidateRuntimeSandboxError) as error:
        owner.verify_sandboxed_java_toolchain(descriptor, receipt.as_dict())
    assert error.value.code == "sandbox_receipt_unauthenticated"
    forged = replace(descriptor, available=True, verified=True,
        enforced_requirements=sandbox.MANDATORY_REQUIREMENTS)
    with pytest.raises(sandbox.CandidateRuntimeSandboxError) as error:
        owner.verify_sandboxed_java_toolchain(forged, receipt)
    assert error.value.code == "sandbox_descriptor_unauthenticated"


def test_authenticated_incomplete_sandbox_binding_is_reported_without_authority(sandbox_blocked, monkeypatch):
    sandbox_descriptor, sandbox_receipt = sandbox_blocked
    monkeypatch.setattr(discovery, "discover_local_java_artifacts", lambda **kwargs: _missing())
    java_descriptor, java_receipt = owner.verify_sandboxed_java_toolchain(sandbox_descriptor, sandbox_receipt)
    assert java_receipt.sandbox_binding_authenticated is True
    assert java_receipt.sandbox_descriptor_fingerprint == sandbox_descriptor.fingerprint
    assert java_receipt.sandbox_verification_receipt_fingerprint == sandbox_receipt.fingerprint
    assert java_receipt.status == owner.UNAVAILABLE
    assert owner.java_toolchain_satisfies_executor_runtime(java_descriptor, sandbox_descriptor) is False
    assert owner.java_toolchain_satisfies_executor_runtime(java_descriptor, sandbox_descriptor.as_dict()) is False


def test_records_are_frozen_and_caller_api_has_no_execution_authority_controls(blocked):
    descriptor, receipt = blocked
    spec = owner.synthetic_java_spec(_pair())
    for record, name, value in ((descriptor, "verified", True), (receipt, "status", "green"),
                               (spec, "shell", True)):
        with pytest.raises(FrozenInstanceError):
            setattr(record, name, value)
    assert {field.name for field in fields(owner.JavaToolchainExecutionSpec) if field.init} == {
        "javac_path", "java_path", "javac_sha256", "java_sha256"}
    for kind in (owner.JavaToolchainExecutionSpec, owner.SandboxedJavaToolchainDescriptor):
        assert not ({"command", "argv", "flags", "main_class", "repository_root", "mounts",
                     "privileged", "host_network", "seccomp_profile", "classpath"}
                    & {field.name for field in fields(kind)})


def test_fixed_source_and_exact_compile_runtime_surfaces_are_phase_owned():
    spec = owner.synthetic_java_spec(_pair())
    assert spec.inputs == (owner.ExactJavaSandboxInput(owner.SOURCE_PATH, owner.JAVA_SOURCE),)
    assert spec.shell is False
    assert spec.compile_argv == (spec.javac_path, *owner.COMPILE_ARGUMENTS)
    assert spec.runtime_argv == (spec.java_path, *owner.RUNTIME_ARGUMENTS)
    assert spec.compile_argv[-3:] == ("-d", "/work/classes", "/work/JavaSandboxProbe.java")
    assert spec.runtime_argv[-3:] == ("-cp", "/work/classes", "JavaSandboxProbe")
    assert spec.timeout_ms == 10000
    assert spec.stdout_limit_bytes == spec.stderr_limit_bytes == 8192
    assert owner.EXPECTED_OUTPUT == b"JAVA_SANDBOX_OK"
    assert b"reflect" not in owner.JAVA_SOURCE.lower()


@pytest.mark.parametrize("path,content", (
    ("../JavaSandboxProbe.java", owner.JAVA_SOURCE), ("/work/JavaSandboxProbe.java", owner.JAVA_SOURCE),
    ("C:\\repo\\bank.java", owner.JAVA_SOURCE), (owner.SOURCE_PATH, b"caller-owned-source"),
    (owner.SOURCE_PATH, bytearray(owner.JAVA_SOURCE)),
))
def test_source_projection_rejects_any_caller_source_or_host_path(path, content):
    with pytest.raises(owner.SandboxedJavaToolchainError) as error:
        owner.ExactJavaSandboxInput(path, content)
    assert error.value.code == "java_input_not_phase_owned"


@pytest.mark.parametrize("change", (
    {"java_path": "C:/jdk/bin/java.exe"}, {"javac_path": "/jdk/bin/javac.exe"},
    {"java_path": "java"}, {"java_path": "/jdk/../bin/java"},
    {"java_path": "/jdk//bin/java"}, {"java_path": "/jdk/bin/java\n"},
    {"java_path": "/bin/sh"}, {"java_sha256": "A" * 64},
    {"javac_sha256": "mutable-tag"}, {"java_sha256": b"a" * 64},
))
def test_executable_identity_rejects_wrong_surface_and_nonexact_binary_hashes(change):
    with pytest.raises(owner.SandboxedJavaToolchainError) as error:
        replace(owner.synthetic_java_spec(_pair()), **change)
    assert error.value.code == "java_executable_identity_invalid"


def test_binary_content_identity_is_bound_into_both_exact_invocation_fingerprints():
    original = owner.synthetic_java_spec(_pair())
    changed = replace(original, javac_sha256="0" * 64)
    assert changed.compile_invocation_identity != original.compile_invocation_identity
    assert changed.runtime_invocation_identity == original.runtime_invocation_identity
    changed = replace(original, java_sha256="0" * 64)
    assert changed.runtime_invocation_identity != original.runtime_invocation_identity
    assert changed.compile_invocation_identity == original.compile_invocation_identity


def test_complete_fabricated_facts_are_only_a_pure_predicate_control():
    spec = owner.synthetic_java_spec(_pair())
    assert owner._java_failure(_capture(), _facts(spec), True, spec) == ""


@pytest.mark.parametrize("key,value", (
    ("uid", 0), ("pid_is_one", False), ("no_new_privileges", False),
    ("capabilities_zero", False), ("descendants_contained", False),
))
def test_any_weakened_privilege_or_descendant_boundary_fails(key, value):
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec); facts[key] = value
    assert owner._java_failure(_capture(), facts, True, spec) == "java_runtime_boundary_incomplete"


@pytest.mark.parametrize("key,value", (("JAVA_TOOL_OPTIONS", "-agentlib:caller"),
    ("JAVA_HOME", "/host-jdk"), ("CATTUS_SANDBOX_HOST_ONLY", "host-secret")))
def test_closed_environment_equality_rejects_inherited_image_or_host_values(key, value):
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec); facts["environment"][key] = value
    assert owner._java_failure(_capture(), facts, True, spec) == "java_runtime_boundary_incomplete"


@pytest.mark.parametrize("key,value,reason", (
    ("source_sha256", "0" * 64, "java_source_projection_mismatch"),
    ("source_size_bytes", 0, "java_source_projection_mismatch"),
    ("javac_binary_sha256", "0" * 64, "java_executable_identity_mismatch"),
    ("java_binary_sha256", "0" * 64, "java_executable_identity_mismatch"),
))
def test_projected_source_and_in_sandbox_binary_hashes_must_match_exact_inputs(key, value, reason):
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec); facts[key] = value
    assert owner._java_failure(_capture(), facts, True, spec) == reason


@pytest.mark.parametrize("stage", ("javac_identity", "java_identity", "javac", "java"))
def test_every_toolchain_stage_must_use_exact_fixed_arguments(stage):
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec); facts["stages"][stage]["argv"].append("caller-flag")
    assert owner._java_failure(_capture(), facts, True, spec) == "java_invocation_identity_mismatch"


def test_extra_invocations_and_missing_compiler_or_runtime_identity_cannot_verify():
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec)
    facts["stages"]["caller_scenario"] = _stage(("/bin/sh",))
    assert owner._java_failure(_capture(), facts, True, spec) == "java_invocation_identity_mismatch"
    for name, reason in (("javac_identity", "java_compiler_identity_missing"),
                         ("java_identity", "java_runtime_identity_missing")):
        facts = _facts(spec)
        facts["stages"][name]["stdout_b64"] = facts["stages"][name]["stderr_b64"] = ""
        assert owner._java_failure(_capture(), facts, True, spec) == reason


@pytest.mark.parametrize("stream", ("stdout", "stderr"))
def test_successful_compile_with_unexpected_diagnostics_still_fails(stream):
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec)
    facts["stages"]["javac"][stream + "_b64"] = base64.b64encode(b"unexpected diagnostic").decode()
    assert owner._java_failure(_capture(), facts, True, spec) == "java_compile_diagnostics_unexpected"


def test_compile_failure_is_measured_failure_and_probe_is_not_repaired():
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec)
    facts["stages"]["javac"] = _stage(spec.compile_argv, stderr=b"fixed bounded diagnostic", exit_code=1)
    before = deepcopy(facts)
    assert owner._java_failure(_capture(), facts, True, spec) == "java_compile_failure"
    assert facts == before


def test_seccomp_startup_failure_is_incompatible_and_does_not_change_frozen_profile():
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec)
    facts["stages"]["java"] = _stage(spec.runtime_argv, stderr=b"Operation not permitted", exit_code=1)
    before = deepcopy(sandbox._SECCOMP)
    assert owner._java_failure(_capture(), facts, True, spec) == "sandbox_java_incompatible:java_failed"
    assert sandbox._SECCOMP == before
    assert "clone3" in sandbox._DENIED_SYSCALLS


@pytest.mark.parametrize("stdout,stderr", (
    (b"JAVA_SANDBOX_OK\n", b""), (b"", b""),
    (owner.EXPECTED_OUTPUT, b"unexpected diagnostic"), (b"product behavior", b""),
))
def test_runtime_probe_output_must_equal_exact_bounded_infrastructure_marker(stdout, stderr):
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec); facts["stages"]["java"] = _stage(spec.runtime_argv, stdout=stdout, stderr=stderr)
    assert owner._java_failure(_capture(), facts, True, spec) == "java_probe_output_mismatch"


@pytest.mark.parametrize("change", (
    {"path": "bank.class"}, {"path": "../JavaSandboxProbe.class"}, {"sha256": "bad"},
    {"size_bytes": 0}, {"size_bytes": True}, {"size_bytes": 32769},
))
def test_class_output_must_be_one_bounded_hashed_phase_owned_class(change):
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec); facts["class_manifest"][0].update(change)
    assert owner._java_failure(_capture(), facts, True, spec) == "java_class_output_mismatch"


def test_any_remaining_container_source_class_or_descendant_revokes_verification():
    spec = owner.synthetic_java_spec(_pair())
    assert owner._java_failure(_capture(), _facts(spec), False, spec) == "java_cleanup_not_verified"


@pytest.mark.parametrize("stream", ("stdout", "stderr"))
@pytest.mark.parametrize("stage,bound", (("javac_identity", 1024), ("java_identity", 1024),
    ("javac", 2048), ("java", 1024)))
def test_each_stage_stream_has_an_independent_hard_bound(stream, stage, bound):
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec)
    facts["stages"][stage][stream + "_b64"] = base64.b64encode(b"x" * (bound + 1)).decode()
    assert owner._java_failure(_capture(), facts, True, spec) == "java_output_limit_exceeded"


def test_outer_timeout_and_stream_bounds_use_frozen_hard_control_receipt():
    spec = owner.synthetic_java_spec(_pair())
    facts = _facts(spec)
    assert owner._java_failure(_capture("sandbox_timeout"), facts, True, spec) == "sandbox_java_incompatible:sandbox_timeout"
    assert owner._java_failure(_capture(within_deadline=False), facts, True, spec) == "java_hard_timeout_not_verified"
    for stream in ("stdout", "stderr"):
        assert owner._java_failure(_capture(**{stream: b"x" * 8193}), facts, True, spec) == "java_output_limit_exceeded"


def _safe_configuration():
    return {
        "Image": "sha256:" + "1" * 64, "Mounts": [],
        "HostConfig": {
            "Privileged": False, "NetworkMode": "none", "PidMode": "", "IpcMode": "none",
            "CgroupnsMode": "private", "ReadonlyRootfs": True, "Binds": None, "Mounts": None,
            "CapDrop": ["ALL"], "CapAdd": None, "LogConfig": {"Type": "none"},
            "PidsLimit": 128, "Memory": 134217728, "NanoCpus": 1000000000,
            "Tmpfs": {"/work": "rw,nosuid,nodev,size=32m,mode=1777",
                      "/tmp": "rw,nosuid,nodev,noexec,size=16m,mode=1777"},
            "SecurityOpt": ["no-new-privileges=true", "seccomp=" + sandbox._json(sandbox._SECCOMP)],
        },
        "Config": {
            "User": "65534:65534", "WorkingDir": "/work", "Entrypoint": ["/usr/local/bin/python"],
            "Cmd": ["-I", "-S", "-B", "-c", owner.JAVA_PROBE_SOURCE],
            "Env": [key + "=" + value for key, value in sandbox._WORKLOAD_ENVIRONMENT.items()],
        },
    }


@pytest.mark.parametrize("section,key,value", (
    ("HostConfig", "Privileged", True), ("HostConfig", "NetworkMode", "host"),
    ("HostConfig", "PidMode", "host"), ("HostConfig", "ReadonlyRootfs", False),
    ("HostConfig", "Binds", ["C:/repository:/work"]), ("HostConfig", "CapAdd", ["SYS_ADMIN"]),
    ("HostConfig", "CapDrop", []), ("HostConfig", "SecurityOpt", ["seccomp=unconfined"]),
    ("Config", "User", "0:0"), ("Config", "WorkingDir", "/repository"),
    ("Config", "Entrypoint", ["/bin/sh"]), ("Config", "Cmd", ["-c", "caller-owned-code"]),
    ("Config", "Env", ["JAVA_HOME=/caller-jdk"]),
))
def test_changed_image_configuration_cannot_reuse_frozen_flags_without_inspection(section, key, value):
    config = _safe_configuration()
    assert owner._safe_java_configuration(config, config["Image"]) is True  # Predicate control only.
    config[section][key] = value
    assert owner._safe_java_configuration(config, config["Image"]) is False


def test_mutable_image_identity_or_repository_mount_cannot_pass_configuration():
    config = _safe_configuration()
    assert owner._safe_java_configuration(config, "sha256:" + "2" * 64) is False
    config["Mounts"] = [{"Type": "bind", "Source": "C:/repository", "Destination": "/work"}]
    assert owner._safe_java_configuration(config, config["Image"]) is False
