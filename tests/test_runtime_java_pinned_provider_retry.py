"""Pure retry controls; virtual transports establish no live provider claim."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import secrets
import sys
import tempfile

import pytest

from tests.test_runtime_java_pinned_provider import (
    guarded, control, runtime_control, issued, owner, bind, _validate, _upstreams)


_HELPER_PATH = Path(__file__).resolve().parents[1] / (
    "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C_RETRY/authentication_controls.py")
_SPEC = importlib.util.spec_from_file_location("pinned1c_retry_authentication_controls", _HELPER_PATH)
controls = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(controls)


def _private_path():
    return str(Path(tempfile.gettempdir()) /
        ("runtime-sandbox1-no-config-" + secrets.token_hex(16)))


def test_random_distinct_bind_and_runtime_private_configs_accept_exact_backend(control, runtime_control, monkeypatch):
    bind_path, runtime_path = _private_path(), _private_path()
    assert bind_path != runtime_path and not Path(bind_path).exists() and not Path(runtime_path).exists()
    bind_prefixes = []

    def configure_bind(controlled):
        controlled.prefix = (*controlled.prefix[:2], bind_path, *controlled.prefix[3:])
        bind.sandbox._docker_prefix.return_value = controlled.prefix
        bind_prefixes.append(controlled.prefix)

    control.configure_bind = configure_bind
    runtime_control.prefix = (*runtime_control.prefix[:2], runtime_path, *runtime_control.prefix[3:])
    result = owner.issue_pinned_java_exact_provider()
    assert result.status == owner.COMPLETE, result.reason
    assert bind_prefixes[0][2] == bind_path != runtime_control.prefix[2]
    assert _validate(result) is result.receipt
    upstreams = _upstreams(result)
    assert bind.validate_sandbox_backend_binding(*upstreams[1:4]) is upstreams[1]
    assert upstreams[1].canonical_backend_identity == result.as_dict()["runtime_backend_pre"][0]
    assert upstreams[1].canonical_backend_version == result.as_dict()["runtime_backend_pre"][1]
    assert all(row["absent"] is True for row in result.as_dict()["private_empty_config_path_measurements"])
    assert not Path(bind_path).exists() and not Path(runtime_path).exists()


@pytest.mark.parametrize("change", ["route", "version"])
def test_backend_route_or_version_difference_rejects(issued, change):
    record = owner._ATTACHMENTS[issued.attachment.receipt_id]
    original = record["measurement"]
    candidate = deepcopy(original)
    index = 0 if change == "route" else 1
    candidate["pre"][index] = candidate["post"][index] = "changed"
    try:
        record["measurement"] = candidate
        with pytest.raises(ValueError):
            _validate(issued)
    finally:
        record["measurement"] = original
    assert _validate(issued) is issued.receipt


@pytest.mark.parametrize("change", ["alias", "reconstruction"])
def test_caller_config_alias_and_report_reconstruction_reject(issued, change):
    values = list(_upstreams(issued))
    if change == "reconstruction":
        values[9] = json.loads(json.dumps(values[9].as_dict()))
        with pytest.raises(ValueError):
            owner.validate_pinned_java_exact_provider(issued.receipt, *values)
    else:
        record = owner._ATTACHMENTS[issued.attachment.receipt_id]
        original = record["measurement"]
        candidate = deepcopy(original)
        candidate["runtime_prefix"][2] = "caller-private-config-alias"
        try:
            record["measurement"] = candidate
            with pytest.raises(ValueError):
                _validate(issued)
        finally:
            record["measurement"] = original
    assert _validate(issued) is issued.receipt


@pytest.fixture
def observer_transport(monkeypatch):
    calls = []
    # Invoke the original namespace generator through a known external CLI path.
    monkeypatch.setattr(owner.sandbox.shutil, "which", lambda name: "C:/Program Files/Docker/docker.exe")
    monkeypatch.setattr(owner.sandbox, "_local_endpoint", lambda: "npipe:////./pipe/dockerDesktopLinuxEngine")

    def bounded(argv, **kwargs):
        calls.append(argv)
        return None

    monkeypatch.setattr(owner.sandbox, "_bounded_process", bounded)
    return calls


def test_exact_observer_retains_original_paths_and_restores_nested_profile(observer_transport):
    observer = controls.config_observation()
    previous_trace, previous_profile = sys.gettrace(), sys.getprofile()
    with observer:
        prefix_a = owner.sandbox._docker_prefix()
        prefix_b = owner.sandbox._docker_prefix()
        assert prefix_a[2] != prefix_b[2]
        # The frozen provider installs its restricted profiler inside this trace.
        sys.setprofile(lambda frame, event, value: None)
        try:
            owner.sandbox._bounded_process((*prefix_a, "version"))
            owner.sandbox._bounded_process((*prefix_b, "version"))
        finally:
            sys.setprofile(previous_profile)
    assert sys.gettrace() is previous_trace and sys.getprofile() is previous_profile
    assert observer.authenticate() and observer.cleanup_verified
    assert observer.as_dict()["control_calls_authenticated"] == 2
    with pytest.raises(ValueError, match="original_private_config_observation"):
        observer.authenticate(json.loads(json.dumps(observer.records)))


@pytest.mark.parametrize("which", [0, 1])
@pytest.mark.parametrize("when", ["generation", "control", "after"])
def test_each_private_config_absence_failure_rejects(observer_transport, monkeypatch, which, when):
    observer = controls.config_observation()
    original_absent = controls._absent
    paths = []

    def measured_absence(path):
        if when == "generation" and len(paths) == which + 1 and path == paths[which]:
            return False
        if when != "generation" and len(paths) == 2 and path == paths[which]:
            return False
        return original_absent(path)

    if when == "generation":
        original_token = owner.sandbox.secrets.token_hex
        tokens = [secrets.token_hex(16), secrets.token_hex(16)]
        paths[:] = [str(Path(tempfile.gettempdir()) / ("runtime-sandbox1-no-config-" + token)) for token in tokens]
        # Only the selected generated path fails its own absence predicate.
        monkeypatch.setattr(controls, "_absent", lambda path: False if path == paths[which] else original_absent(path))
        monkeypatch.setattr(owner.sandbox.secrets, "token_hex", lambda count: tokens.pop(0))
        with pytest.raises(ValueError, match="not_absent_at_generation"):
            with observer:
                owner.sandbox._docker_prefix()
                owner.sandbox._docker_prefix()
    else:
        with pytest.raises(ValueError, match="not_absent_before_control|absence_after_use"):
            with observer:
                prefixes = [owner.sandbox._docker_prefix(), owner.sandbox._docker_prefix()]
                paths[:] = [prefix[2] for prefix in prefixes]
                if when == "control":
                    monkeypatch.setattr(controls, "_absent", measured_absence)
                    owner.sandbox._bounded_process((*prefixes[which], "version"))
                else:
                    owner.sandbox._bounded_process((*prefixes[0], "version"))
                    owner.sandbox._bounded_process((*prefixes[1], "version"))
                    monkeypatch.setattr(controls, "_absent", measured_absence)
    assert sys.gettrace() is None and sys.getprofile() is None
    assert len(observer_transport) == (2 if when == "after" else 0)


@pytest.mark.parametrize("kind", ["alias", "reconstruction", "changed_route"])
def test_observer_rejects_unowned_or_reconstructed_config_before_control(observer_transport, kind):
    observer = controls.config_observation()
    with pytest.raises(ValueError, match="original_generator_provenance"):
        with observer:
            prefix = owner.sandbox._docker_prefix()
            changed = list(prefix)
            if kind == "alias": changed[2] = _private_path()
            elif kind == "reconstruction": changed[2] = json.loads(json.dumps(prefix[2]))
            else: changed[4] = "caller-endpoint"
            owner.sandbox._bounded_process((*changed, "version"))
    assert observer_transport == []
    assert sys.gettrace() is None


@pytest.mark.parametrize("instrument", ["trace", "profile", "thread_trace", "thread_profile"])
def test_retry_observer_preexisting_instrumentation_blocks_before_effect(observer_transport, instrument):
    module = controls.threading if instrument.startswith("thread_") else sys
    name = instrument.removeprefix("thread_")
    getter, setter = getattr(module, "get" + name), getattr(module, "set" + name)
    previous = getter()
    callback = lambda frame, event, value: None
    try:
        setter(callback)
        with pytest.raises(ValueError, match="instrumentation_already_owned"):
            with controls.config_observation():
                pytest.fail("observer entered despite existing instrumentation")
        assert getter() is callback
    finally:
        setter(previous)
    assert observer_transport == []


def test_retry_live_matrix_rejects_all_controls_and_restores_exact_originals(issued, monkeypatch):
    before = deepcopy(issued.as_dict())
    record = owner._ATTACHMENTS[issued.attachment.receipt_id]
    original_measurement = record["measurement"]
    monkeypatch.setattr(owner.pinned, "issue_pinned_backend_target_binding",
        lambda: pytest.fail("negative controls must not issue a second live graph"))
    monkeypatch.setattr(owner.runtime, "verify",
        lambda: pytest.fail("negative controls must not issue a second runtime"))
    matrix = controls.retry_negative_authentication_matrix(issued)
    assert matrix["controls"] and matrix["all_controls_rejected"]
    assert all(type(value) is bool and value for value in matrix["controls"].values())
    assert all(matrix["originals_reauthenticated_after_controls"].values())
    assert matrix["additional_live_owner_issuances"] == 0
    assert "no second live graph claim" in matrix["different_fresh_candidate_semantics"]
    assert record["measurement"] is original_measurement
    assert issued.as_dict() == before and _validate(issued) is issued.receipt
