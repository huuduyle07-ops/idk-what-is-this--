"""Pure exact-provider graph tests through every unchanged public issuer.

The transports and measurements below are controlled test fixtures. They do
not inspect Docker or establish a live provider proof. Original JAVA.1C verify
and invocation frames remain in use so the additive observer is exercised.
"""
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import runtime_java_pinned_provider as owner
    from core import runtime_java_pinned_backend_target_binding as binding
    from core import runtime_java_pinned_target_inspection as target
    from core import sandbox_backend_binding as bind
    from core import sandboxed_java_positive_continuation as runtime
    from core import sandboxed_java_positive_probe as probe
    from tests.test_runtime_java_pinned_backend_target_binding import control
    from tests.test_runtime_java1c import capture, facts, safe_config
    from tests.test_runtime_java1b import stage_facts


_ENDPOINT = "npipe:////./pipe/dockerDesktopLinuxEngine"
_ROUTE = "local-docker:" + _ENDPOINT
_VERSION = " Exact.01 "
_CONTROLLER_HASH = "0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263"
_FALSE_CLAIMS = (
    "runtime_authority", "real_task_runtime_authority", "repository_write_authority",
    "apply_authority", "compatibility_authority", "SYNTH_authority", "executor_authority",
    "complete_inventory_claimed", "complete_local_artifact_discovery_claimed",
    "global_provider_absence_claimed", "global_provider_uniqueness_claimed",
    "daemon_identity_claimed", "daemon_continuity_claimed", "aba_resistance_claimed",
)


@pytest.fixture(autouse=True)
def guarded():
    with no_runtime_effects(strict=True) as effects, \
            patch("threading.Thread.start", side_effect=effects.deny("thread_start")), \
            patch.dict(bind._LIVE, {}, clear=True), \
            patch.dict(target._LIVE, {}, clear=True), \
            patch.dict(binding._LIVE, {}, clear=True), \
            patch.dict(binding._ATTEMPTS, {}, clear=True), \
            patch.dict(binding._UPSTREAM_ORIGINS, {}, clear=True), \
            patch.dict(owner._LIVE, {}, clear=True), \
            patch.dict(owner._ATTACHMENTS, {}, clear=True), \
            patch.dict(owner._ATTEMPTS, {}, clear=True), \
            patch.dict(owner._ORIGINS, {}, clear=True):
        yield
    assert effects.denied_attempts == {}


@pytest.fixture
def runtime_control(control, monkeypatch):
    """Virtual transports preserve the actual JAVA.1C owner and frame locals."""
    def configure_target(controlled):
        controller = replace(controlled.archive.controller, sha256=_CONTROLLER_HASH,
            ancestor_metadata_complete=False,
            ancestor_traversal_paths=(("/", None), ("/usr", True),
                ("/usr/local", True), ("/usr/local/bin", True)))
        controlled.archive = replace(controlled.archive, controller=controller)
    control.configure_target = configure_target

    state = SimpleNamespace(prefix=("fixed-docker.exe", "--config", "absent", "--host", _ENDPOINT),
        commands=[], version_values=[_VERSION, _VERSION], version_calls=0,
        facts=facts(), config=safe_config(),
        metadata={"Id": runtime.IMAGE, "Os": "linux", "Architecture": "amd64", "Config": {"Volumes": {}}},
        sandbox_runs=0, active_workspace=False, remaining=0, captures={},
        workspace="C:/fixture/pinned-provider-runtime", workspace_removed=True)
    state.config["Id"] = "e" * 64

    def measured(argv, **kwargs):
        assert argv[:2] == state.prefix[:2] and argv[3:5] == state.prefix[3:5]
        command = tuple(argv[len(state.prefix):])
        state.commands.append((command, kwargs))
        role = command[0]
        if role == "version":
            index = state.version_calls
            state.version_calls += 1
            value = state.version_values[min(index, len(state.version_values) - 1)]
            result = capture(stdout=json.dumps({"Server": {"Os": "linux", "Version": value}}).encode())
        elif command[:2] == ("image", "inspect"):
            assert command[2] == runtime.IMAGE
            role = "image"
            result = capture(stdout=json.dumps(state.metadata).encode())
        elif role == "create":
            state.name = command[command.index("--name") + 1]
            assert command[command.index("--entrypoint") + 1] == "/usr/local/bin/python"
            assert command[-5:] == ("-I", "-S", "-B", "-c", probe.source())
            result = capture(stdout=b"e" * 64)
        elif role == "inspect" and command[-1] == "{{json .}}":
            assert command[1] == state.name
            role = "configuration"
            result = capture(stdout=json.dumps(state.config).encode())
        elif role == "start":
            assert command == ("start", "--attach", "--interactive", state.name)
            result = capture(stdout=json.dumps({"facts": state.facts}).encode())
        elif role in ("kill", "rm"):
            assert command[1 if role == "kill" else -1] == state.name
            result = capture()
        elif role == "inspect":
            assert command[1] == state.name
            role = "absence"
            result = capture(exit_code=1, stderr=b"No such object: controlled runtime")
        elif role == "ps":
            result = capture(stdout=b"remaining\n" * state.remaining)
        else:
            pytest.fail("Unexpected provider control: " + repr(command))
        return state.captures.get(role, result)

    def fresh_sandbox():
        state.sandbox_runs += 1
        compiler, jvm = stage_facts(), stage_facts()
        jvm["stages"]["javac_identity"]["argv"] = [probe.JAVA_PATH, "-version"]
        stages = [{"mode": mode, "verdict": runtime.sandbox2.PASSED,
            "cleanup_verified": True,
            "facts": compiler if mode == "javac_version" else jvm if mode == "java_version" else {}}
            for mode in runtime.sandbox2.LADDER]
        live = {"status": runtime.sandbox2.COMPLETE, "cleanup_verified": True,
            "temporary_workspace_removed": True, "phase_container_count_after_teardown": 0,
            "javac_version_count": 1, "java_version_count": 1, "compile_count": 0,
            "jvm_fixture_count": 0, "stages": stages}
        sd, sr = runtime.sandbox2._evidence_pair(live)
        live.update(descriptor=sd.as_dict(), verification_receipt=sr.as_dict())
        return live

    @contextmanager
    def workspace(*args, **kwargs):
        assert kwargs.get("prefix") == "runtime-java1c-profile-"
        state.active_workspace = True
        try:
            yield state.workspace
        finally:
            state.active_workspace = False

    original_read, original_exists = Path.read_bytes, Path.exists

    def read(path):
        if str(path).replace("\\", "/") == state.workspace + "/seccomp.json":
            return runtime.sandbox2.POLICY_BYTES
        return original_read(path)

    def write(path, content):
        assert str(path).replace("\\", "/") == state.workspace + "/seccomp.json"
        assert state.active_workspace and content == runtime.sandbox2.POLICY_BYTES
        return len(content)

    def exists(path):
        if str(path).replace("\\", "/") == state.workspace:
            return state.active_workspace or not state.workspace_removed
        return original_exists(path)

    def entries(path):
        assert str(path).replace("\\", "/") == state.workspace and state.active_workspace
        return iter((Path(state.workspace) / "seccomp.json",))

    monkeypatch.setattr(runtime.baseline, "_docker_prefix", lambda: state.prefix)
    monkeypatch.setattr(runtime.baseline, "_local_endpoint", lambda: _ENDPOINT)
    monkeypatch.setattr(runtime.baseline, "_bounded_process", measured)
    monkeypatch.setattr(runtime.sandbox2, "replay", fresh_sandbox)
    monkeypatch.setattr(runtime.tempfile, "TemporaryDirectory", workspace)
    monkeypatch.setattr(Path, "read_bytes", read)
    monkeypatch.setattr(Path, "write_bytes", write)
    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(Path, "iterdir", entries)
    return state


@pytest.fixture
def issued(runtime_control):
    previous_profile = sys.getprofile()
    outcome = owner.issue_pinned_java_exact_provider()
    assert sys.getprofile() is previous_profile
    assert outcome.status == owner.COMPLETE, outcome.reason
    assert outcome.receipt is not None
    return outcome


def _upstreams(outcome):
    graph = outcome.pinned_binding
    return (graph.receipt, graph.bind_attachment, graph.sandbox_descriptor,
        graph.sandbox_receipt, graph.inspection_receipt, outcome.runtime_descriptor,
        outcome.runtime_receipt, outcome.sandbox_descriptor, outcome.sandbox_receipt,
        outcome.attachment)


def _validate(outcome, receipt=None, upstreams=None):
    return owner.validate_pinned_java_exact_provider(
        outcome.receipt if receipt is None else receipt,
        *(_upstreams(outcome) if upstreams is None else upstreams))


def _assert_rejected(outcome, *, receipt=None, upstreams=None):
    with pytest.raises(ValueError):
        _validate(outcome, receipt, upstreams)


def test_original_fresh_graph_and_actual_observer_close_provider_only(issued, runtime_control, control):
    upstreams = _upstreams(issued)
    assert _validate(issued) is issued.receipt
    assert owner.validate_runtime_attachment(issued.attachment, *upstreams[:9]) is issued.attachment
    assert binding.validate_pinned_backend_target_binding(*upstreams[:5]) is upstreams[0]
    assert runtime.validate_descriptor(*upstreams[5:7]) is upstreams[5]
    assert runtime.authenticate_sandbox2(*upstreams[7:9]) == upstreams[7:9]
    assert runtime.java_toolchain_satisfies_executor_runtime(*upstreams[5:9]) is True
    assert control.events == ["bind_issue", "bind_done", "inspection_issue", "inspection_done"]
    assert len(control.bind_issues) == len(control.target_issues) == runtime_control.sandbox_runs == 1
    assert runtime_control.version_calls == 2
    assert sum(command[0] == "start" for command, _ in runtime_control.commands) == 1
    assert issued.receipt.phase_id == "RUNTIME.JAVA.PINNED.1C"
    assert issued.receipt.schema_version == "runtime_java_pinned_provider_1c_v1"
    assert issued.receipt.exact_provider_proven is True
    assert issued.attachment.exact_provider_proven is False
    assert issued.receipt.proof_context_identity != upstreams[0].proof_context_identity
    assert issued.receipt.issuing_pid == owner.os.getpid()
    assert all(len(getattr(issued.receipt, field)) == 64 for field in
        ("proof_context_identity", "receipt_id", "evidence_digest", "fingerprint"))
    assert upstreams[2] is not upstreams[7] and upstreams[3] is not upstreams[8]
    assert upstreams[2].fingerprint != upstreams[7].fingerprint
    assert upstreams[3].evidence_sha256 != upstreams[8].evidence_sha256
    assert upstreams[4].archive.controller.ancestor_metadata_complete is False
    assert upstreams[4].archive.controller.sha256 == _CONTROLLER_HASH
    evidence = json.loads(issued.receipt.evidence_json)
    assert evidence and _ROUTE in issued.receipt.evidence_json and _VERSION in issued.receipt.evidence_json
    for value in upstreams[:9]:
        assert value.fingerprint in issued.receipt.evidence_json
    assert _CONTROLLER_HASH in issued.receipt.evidence_json
    assert "/usr/local/bin/python3.12" in issued.receipt.evidence_json
    with pytest.raises(FrozenInstanceError):
        issued.receipt.owner_identity = "changed"


def test_no_authority_lifecycle_or_effectful_validation(issued, monkeypatch):
    for value in (issued.receipt, issued.attachment):
        assert all(getattr(value, field) is False for field in _FALSE_CLAIMS)
        assert not any(hasattr(value, field) for field in
            ("consume", "invalidate", "lease_id", "lifecycle_state"))
    monkeypatch.setattr(binding, "issue_pinned_backend_target_binding", lambda: pytest.fail("new BIND in validation"))
    monkeypatch.setattr(runtime, "verify", lambda: pytest.fail("new runtime in validation"))
    before = deepcopy(issued.as_dict())
    for _ in range(3):
        assert _validate(issued) is issued.receipt
    assert issued.as_dict() == before
    json.dumps(before, allow_nan=False)


def test_issuer_accepts_no_caller_source_route_or_evidence(runtime_control):
    assert not inspect.signature(owner.issue_pinned_java_exact_provider).parameters
    for supplied in (None, {}, "caller-alias", runtime.IMAGE):
        with pytest.raises(TypeError):
            owner.issue_pinned_java_exact_provider(supplied)
    assert runtime_control.commands == []


@pytest.mark.parametrize("kind", ["copy", "deepcopy", "replace", "json", "reconstruction", "wrapper", "subclass"])
def test_final_root_projection_never_recreates_original_identity(issued, kind):
    original = issued.receipt
    if kind == "copy": candidate = copy(original)
    elif kind == "deepcopy": candidate = deepcopy(original)
    elif kind == "replace": candidate = replace(original)
    elif kind == "json": candidate = json.loads(json.dumps(original.as_dict()))
    elif kind == "wrapper": candidate = SimpleNamespace(**original.as_dict())
    else:
        cls = type(original)
        if kind == "subclass":
            class Subclass(cls): pass
            cls = Subclass
        candidate = cls(**{field.name: getattr(original, field.name) for field in fields(original) if field.init})
    if hasattr(candidate, "fingerprint"):
        assert candidate.fingerprint == original.fingerprint
    _assert_rejected(issued, receipt=candidate)


@pytest.mark.parametrize("role", range(10))
@pytest.mark.parametrize("kind", ["copy", "deepcopy", "json", "alias"])
def test_every_original_upstream_is_required_even_with_matching_fingerprints(issued, role, kind):
    upstreams = list(_upstreams(issued))
    original = upstreams[role]
    if kind == "copy": upstreams[role] = copy(original)
    elif kind == "deepcopy": upstreams[role] = deepcopy(original)
    elif kind == "json": upstreams[role] = json.loads(json.dumps(original.as_dict()))
    else: upstreams[role] = original.fingerprint
    _assert_rejected(issued, upstreams=upstreams)


@pytest.mark.parametrize("role", range(10))
def test_different_authentic_graph_cannot_be_spliced_into_final_root(issued, runtime_control, role):
    other = owner.issue_pinned_java_exact_provider()
    assert other.status == owner.COMPLETE, other.reason
    upstreams = list(_upstreams(issued))
    upstreams[role] = _upstreams(other)[role]
    _assert_rejected(issued, upstreams=upstreams)
    assert _validate(issued) is issued.receipt


@pytest.mark.parametrize("field,value", [
    *[(field, "changed") for field in ("phase_id", "schema_version", "status", "owner_identity",
        "proof_context_identity", "receipt_id", "evidence_json", "evidence_digest")],
    ("issuing_pid", -1), ("_signature", "0" * 64), ("exact_provider_proven", False),
    *[(field, True) for field in _FALSE_CLAIMS],
])
@pytest.mark.parametrize("which", ["receipt", "attachment"])
def test_final_payload_hmac_process_or_forbidden_claim_tampering_is_rejected(issued, field, value, which):
    target_value = getattr(issued, which)
    if which == "attachment" and field == "exact_provider_proven": value = True
    original = getattr(target_value, field)
    object.__setattr__(target_value, field, value)
    try:
        _assert_rejected(issued)
    finally:
        object.__setattr__(target_value, field, original)
    assert _validate(issued) is issued.receipt


@pytest.mark.parametrize("role,field,value", [
    (0, "canonical_backend_route_identity", "changed"),
    (0, "canonical_backend_server_version", "changed"),
    (1, "canonical_backend_identity", "changed"), (1, "canonical_backend_version", "changed"),
    (3, "evidence_sha256", "0" * 64), (3, "cleanup_verified", False),
    (4, "controller_source_identity", ()), (4, "cleanup_evidence", ()),
    (5, "verification_receipt_fingerprint", "0" * 64),
    (6, "java_path", "/changed/java"), (6, "java_sha256", "0" * 64),
    (6, "javac_path", "/changed/javac"), (6, "javac_sha256", "0" * 64),
    (6, "image_identity", "sha256:" + "0" * 64), (6, "evidence_sha256", "0" * 64),
    (7, "seccomp_policy_sha256", "0" * 64),
    (8, "evidence_sha256", "0" * 64), (8, "cleanup_verified", False),
])
def test_upstream_route_identity_policy_digest_and_cleanup_are_reauthenticated(issued, role, field, value):
    upstream = _upstreams(issued)[role]
    original = getattr(upstream, field)
    object.__setattr__(upstream, field, value)
    try:
        _assert_rejected(issued)
    finally:
        object.__setattr__(upstream, field, original)


@pytest.mark.parametrize("field,value", [("normalized_path", "/usr/bin/python"),
    ("resolved_path", "/different/python3.12"), ("sha256", "0" * 64)])
def test_controller_path_only_or_changed_target_bytes_cannot_prove_runtime_identity(issued, field, value):
    measurement = issued.pinned_binding.inspection_receipt.archive.controller
    original = getattr(measurement, field)
    object.__setattr__(measurement, field, value)
    try:
        _assert_rejected(issued)
    finally:
        object.__setattr__(measurement, field, original)


@pytest.mark.parametrize("change", ["post_version", "pre_version", "version_whitespace", "controller_path",
    "controller_source", "image", "image_volume", "root", "mount", "uid", "java_hash", "javac_hash",
    "child_cleanup", "containers", "workspace"])
def test_real_owner_gates_and_bridge_fail_closed_without_alternate_provider(runtime_control, change):
    state = runtime_control
    if change == "post_version": state.version_values[1] = "changed"
    elif change == "pre_version": state.version_values[:] = ["changed", "changed"]
    elif change == "version_whitespace": state.version_values[:] = [_VERSION.strip()] * 2
    elif change == "controller_path": state.config["Config"]["Entrypoint"] = ["/usr/bin/python"]
    elif change == "controller_source": state.config["Config"]["Cmd"][-1] = "raise SystemExit(0)"
    elif change == "image": state.config["Image"] = "sha256:" + "0" * 64
    elif change == "image_volume": state.metadata["Config"]["Volumes"] = {"/usr/local/bin": {}}
    elif change == "root": state.config["HostConfig"]["ReadonlyRootfs"] = False
    elif change == "mount": state.config["HostConfig"]["Binds"] = ["host:/usr/local/bin"]
    elif change == "uid": state.facts["controller_before"]["uid"] = 0
    elif change == "java_hash": state.facts["java_binary_sha256"] = "0" * 64
    elif change == "javac_hash": state.facts["javac_binary_sha256"] = "0" * 64
    elif change == "child_cleanup": state.facts["stages"]["java"]["child_waited"] = False
    elif change == "containers": state.remaining = 1
    else: state.workspace_removed = False
    outcome = owner.issue_pinned_java_exact_provider()
    assert outcome.status != owner.COMPLETE and outcome.receipt is None
    assert state.sandbox_runs <= 1
    assert sum(command[0] == "start" for command, _ in state.commands) <= 1


def test_pinned1b_failure_stops_before_runtime_issuance(control, runtime_control):
    control.bind_version = "changed"
    outcome = owner.issue_pinned_java_exact_provider()
    assert outcome.status != owner.COMPLETE and outcome.receipt is None
    assert runtime_control.commands == [] and runtime_control.sandbox_runs == 0


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64),
    ("resolved_path", "/usr/local/bin/different-python")])
def test_authentic_target_controller_must_match_exact_phase_identity(control, runtime_control, field, value):
    configure = control.configure_target
    def changed(controlled):
        configure(controlled)
        controlled.archive = replace(controlled.archive,
            controller=replace(controlled.archive.controller, **{field: value}))
    control.configure_target = changed
    outcome = owner.issue_pinned_java_exact_provider()
    assert outcome.status != owner.COMPLETE and outcome.receipt is None
    assert runtime_control.sandbox_runs <= 1


@pytest.mark.parametrize("kind", ["old_objects", "report_json", "chronology_only"])
def test_fresh_chronology_cannot_link_historical_or_report_only_java_component(issued, runtime_control, monkeypatch, kind):
    if kind == "old_objects":
        result = (issued.runtime_descriptor, issued.runtime_receipt, issued.as_dict())
    elif kind == "report_json":
        result = (issued.runtime_descriptor.as_dict(), issued.runtime_receipt.as_dict(), issued.as_dict())
    else:
        result = (None, None, {"phase_id": runtime.PHASE_ID, "status": runtime.COMPLETE,
            "happened_after_pinned1b": True, "image_identity": runtime.IMAGE})
    monkeypatch.setattr(runtime, "verify", lambda: result)
    outcome = owner.issue_pinned_java_exact_provider()
    assert outcome.status != owner.COMPLETE and outcome.receipt is None


def test_wrong_process_and_live_registry_removal_reject_final_root(issued, monkeypatch):
    pid = owner.os.getpid()
    monkeypatch.setattr(owner.os, "getpid", lambda: pid + 1)
    _assert_rejected(issued)
    monkeypatch.setattr(owner.os, "getpid", lambda: pid)
    owner._LIVE.clear()
    _assert_rejected(issued)


def test_pure_negative_matrix_and_repeated_validation_preserve_originals(issued):
    before = deepcopy(issued.as_dict())
    matrix = owner.negative_authentication_matrix(issued)
    assert matrix and all(type(value) is bool and value for value in matrix.values())
    assert issued.as_dict() == before
    assert _validate(issued) is issued.receipt


def test_observer_restores_prior_profiler_after_failed_runtime(runtime_control):
    previous_profile = sys.getprofile()
    runtime_control.facts["java_binary_sha256"] = "0" * 64
    outcome = owner.issue_pinned_java_exact_provider()
    assert outcome.status != owner.COMPLETE and outcome.receipt is None
    assert sys.getprofile() is previous_profile


@pytest.mark.parametrize("change", ["route", "version", "chronology_only", "controller_path_only",
    "controller_source", "image", "java", "javac", "runtime_pair_digest", "runtime_digest",
    "backend_cleanup", "runtime_control_cleanup", "traversal", "policy", "readonly", "mount",
    "volume", "different_control_route"])
def test_attachment_revalidates_complete_observed_relation(issued, change):
    record = owner._ATTACHMENTS[issued.attachment.receipt_id]
    measurement = record["measurement"]
    saved = deepcopy(measurement)
    if change == "route": measurement["pre"][0] = measurement["post"][0] = "local-docker:caller-alias"
    elif change == "version": measurement["pre"][1] = measurement["post"][1] = "changed"
    elif change == "chronology_only": measurement["controls"] = []
    elif change == "controller_path_only": measurement["configuration"] = {"Config": {"Entrypoint": ["/usr/local/bin/python"]}}
    elif change == "controller_source": measurement["configuration"]["Config"]["Cmd"][-1] = "raise SystemExit(0)"
    elif change == "image": measurement["metadata"]["Id"] = "sha256:" + "0" * 64
    elif change == "java": measurement["facts"]["java_binary_sha256"] = "0" * 64
    elif change == "javac": measurement["facts"]["javac_binary_sha256"] = "0" * 64
    elif change == "runtime_pair_digest": measurement["runtime_report"]["live_sandbox2"]["stages"][0]["verdict"] = "changed"
    elif change == "runtime_digest": measurement["facts"]["source_sha256"] = "0" * 64
    elif change == "backend_cleanup": measurement["backend_controls"][0]["control_reaped_and_pipes_closed"] = False
    elif change == "runtime_control_cleanup": measurement["controls"][0]["control_reaped_and_pipes_closed"] = False
    elif change == "traversal": measurement["facts"]["controller_before"]["uid"] = 0
    elif change == "policy": measurement["configuration"]["HostConfig"]["SecurityOpt"] = ["seccomp=unconfined"]
    elif change == "readonly": measurement["configuration"]["HostConfig"]["ReadonlyRootfs"] = False
    elif change == "mount": measurement["configuration"]["Mounts"] = [{"Destination": "/usr/local/bin"}]
    elif change == "volume": measurement["metadata"]["Config"]["Volumes"] = {"/usr/local/bin": {}}
    else: measurement["controls"][0]["argv"][4] = "different-endpoint"
    try:
        _assert_rejected(issued)
    finally:
        record["measurement"] = saved
    assert _validate(issued) is issued.receipt


def test_missing_actual_invocation_observation_never_issues_attachment(runtime_control, monkeypatch):
    original = owner._runtime_snapshot
    def missing():
        snapshot = original()
        snapshot["invoke"] = []
        return snapshot
    monkeypatch.setattr(owner, "_runtime_snapshot", missing)
    result = owner.issue_pinned_java_exact_provider()
    assert result.status == owner.RUNTIME_MISMATCH and result.receipt is result.attachment is None
    assert runtime_control.sandbox_runs == 1


def test_prior_profiler_blocks_before_any_upstream_effect(runtime_control):
    profiler = lambda *args: None
    previous = sys.getprofile()
    try:
        sys.setprofile(profiler)
        result = owner.issue_pinned_java_exact_provider()
        assert result.status == owner.UNRESOLVED and result.receipt is None
        assert sys.getprofile() is profiler
        assert runtime_control.commands == []
    finally:
        sys.setprofile(previous)


def test_observer_restores_profiler_even_when_public_owner_raises(monkeypatch):
    def failed():
        raise RuntimeError("controlled_failure")
    monkeypatch.setattr(runtime, "verify", failed)
    with pytest.raises(RuntimeError, match="controlled_failure"):
        owner._runtime_snapshot()
    assert sys.getprofile() is None


def test_same_binding_replay_stops_before_second_runtime_invocation(issued, runtime_control, monkeypatch):
    monkeypatch.setattr(binding, "issue_pinned_backend_target_binding", lambda: issued.pinned_binding)
    calls = len(runtime_control.commands)
    result = owner.issue_pinned_java_exact_provider()
    assert result.status == owner.BACKEND_MISMATCH and result.receipt is None
    assert len(runtime_control.commands) == calls


def test_frozen_fresh_empty_docker_config_paths_do_not_change_backend_identity(runtime_control, monkeypatch):
    prefixes = []
    def fresh_prefix():
        prefix = (*runtime_control.prefix[:2], "absent-config-" + str(len(prefixes)), *runtime_control.prefix[3:])
        prefixes.append(prefix)
        return prefix
    monkeypatch.setattr(runtime.baseline, "_docker_prefix", fresh_prefix)
    outcome = owner.issue_pinned_java_exact_provider()
    assert outcome.status == owner.COMPLETE, outcome.reason
    assert len(prefixes) == 2 and prefixes[0][2] != prefixes[1][2]
    assert _validate(outcome) is outcome.receipt
    evidence = json.loads(outcome.receipt.evidence_json)
    assert evidence["canonical_backend_route"] == _ROUTE
    assert len(evidence["private_empty_config_path_measurements"]) == 2


def test_existing_docker_configuration_path_cannot_replace_frozen_empty_configuration(runtime_control, monkeypatch):
    original = Path.exists
    monkeypatch.setattr(Path, "exists", lambda path: True if str(path) == "absent" else original(path))
    outcome = owner.issue_pinned_java_exact_provider()
    assert outcome.status == owner.BACKEND_MISMATCH and outcome.receipt is None
