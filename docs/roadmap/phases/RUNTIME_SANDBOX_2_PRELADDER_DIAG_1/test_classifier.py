"""Pure failure localization and observer contracts; no live owner or Docker.

Every test blocks process launch before a child can be created. The sole
SANDBOX.2 issuance helper exercised here is _evidence_pair on fixture facts;
replay, invoke, Docker controls, Java owners and SYNTH owners are never called.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import sys
import threading

import pytest


HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "sandbox2_preladder_pure_diagnostic", HERE / "diagnostic.py")
assert _SPEC is not None and _SPEC.loader is not None
diag = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(diag)

LEDGER = diag.static_ledger()
METADATA_STEPS = (
    "metadata_prefix_requirement", "metadata_id_requirement",
    "metadata_os_requirement", "metadata_arch_requirement",
    "metadata_volumes_requirement",
)
FROZEN_PREFIX = (
    "C:/Program Files/Docker/Docker/resources/bin/docker.exe", "--config",
    "C:/fixture/runtime-sandbox1-no-config-pure", "--host", diag.ENDPOINT,
)


@pytest.fixture(autouse=True)
def no_child_processes(monkeypatch):
    """A swallowed launch attempt also fails the test during teardown."""
    attempts = []

    def forbidden_launch(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError("pure test attempted a process launch")

    monkeypatch.setattr(subprocess, "Popen", forbidden_launch)
    yield attempts
    assert attempts == [], "Docker/shell/control children are forbidden in pure tests"


def all_pass():
    return {row["step"]: "PASS" for row in diag.static_ledger()}


def image_metadata(**changes):
    value = {"Id": diag.IMAGE, "Os": "linux", "Architecture": "amd64", "Config": {}}
    value.update(changes)
    return value


def metadata_rows(states):
    result = all_pass()
    # Unobserved terms must remain unobserved, including short-circuit terms.
    for name in METADATA_STEPS:
        result.pop(name)
    result.update(states)
    failed = next((name for name, value in states.items() if value["state"] == "FAIL"), None)
    if failed is not None:
        after = False
        for row in diag.static_ledger():
            if after:
                result[row["step"]] = "NOT_REACHED"
            after = after or row["step"] == failed
    classified = diag.classify_steps(result)
    rows = {row["step"]: row for row in classified["ordered_pre_ladder_ledger"]}
    return classified, rows


@pytest.mark.parametrize("failure", LEDGER, ids=lambda row: row["step"])
def test_each_static_failure_is_the_first_exact_failure(failure):
    states = all_pass()
    after = False
    for row in diag.static_ledger():
        if after:
            states[row["step"]] = "NOT_REACHED"
        after = after or row["step"] == failure["step"]
    states[failure["step"]] = {
        "state": "FAIL", "error": "fixture operation failure",
        "original_exit_code": 7, "retained_evidence": {"bytes": [0, 255]},
    }
    before = deepcopy(states)
    result = diag.classify_steps(states)
    rows = result["ordered_pre_ladder_ledger"]
    first = result["first_failing_step"]
    assert first["step"] == failure["step"]
    assert first["source"] == failure["source"]
    assert first["function"] == failure["function"]
    assert first["line"] == failure["line"]
    assert result["classification"] == failure["failure_category"]
    assert first["original_exit_code"] == 7
    assert first["retained_evidence"] == {"bytes": [0, 255]}
    index = next(i for i, row in enumerate(rows) if row["step"] == failure["step"])
    assert all(row["state"] == "PASS" for row in rows[:index])
    assert rows[index]["state"] == "FAIL"
    assert all(row["state"] == "NOT_REACHED" for row in rows[index + 1:])
    assert states == before, "classification must preserve supplied evidence"
    first["retained_evidence"]["bytes"].append(8)
    assert states == before, "returned evidence must not alias caller input"


def test_multiple_reported_failures_select_source_order_not_input_order():
    rows = diag.static_ledger()
    states = dict(reversed(list(all_pass().items())))
    states[rows[-1]["step"]] = "FAIL"
    states[rows[1]["step"]] = "FAIL"
    result = diag.classify_steps(states)
    assert result["first_failing_step"]["step"] == rows[1]["step"]
    assert sum(row["state"] == "FAIL" for row in result["ordered_pre_ladder_ledger"]) == 2


def test_failed_image_exit_and_later_actual_id_rejection_are_both_retained():
    states = all_pass()
    exit_index = next(i for i, row in enumerate(diag.static_ledger())
                      if row["step"] == "image_capture_exit_requirement")
    for row in diag.static_ledger()[exit_index + 1:]:
        states[row["step"]] = "NOT_REACHED"
    states["image_capture_exit_requirement"] = {
        "state": "FAIL", "original_exit_code": 1, "capture_status": "sandbox_completed",
    }
    # Frozen replay selects metadata={} without parsing when inspect exits 1,
    # then evaluates prefix and Id; those later measured states remain truthful.
    states.update(diag.metadata_states(FROZEN_PREFIX, {}))
    result = diag.classify_steps(states)
    rows = {row["step"]: row for row in result["ordered_pre_ladder_ledger"]}
    assert result["first_failing_step"]["step"] == "image_capture_exit_requirement"
    assert result["classification"] == "EXACT_IMAGE_INSPECTION_FAILURE"
    assert rows["image_capture_exit_requirement"]["state"] == "FAIL"
    assert rows["image_capture_exit_requirement"]["original_exit_code"] == 1
    assert rows["image_output_parse"]["state"] == "NOT_REACHED"
    assert rows["metadata_prefix_requirement"]["state"] == "PASS"
    assert rows["metadata_id_requirement"]["state"] == "FAIL"
    assert rows["metadata_os_requirement"]["state"] == "NOT_REACHED"
    assert rows["temporary_workspace_create"]["state"] == "NOT_REACHED"


def test_completed_ledger_requires_every_step_observed_pass():
    result = diag.classify_steps(all_pass())
    assert result["classification"] == "PRELADDER_COMPLETE"
    assert result["first_failing_step"] is None
    assert all(row["state"] == "PASS" for row in result["ordered_pre_ladder_ledger"])


@pytest.mark.parametrize("missing", LEDGER, ids=lambda row: row["step"])
def test_unobserved_step_cannot_be_assumed_success(missing):
    states = all_pass()
    del states[missing["step"]]
    result = diag.classify_steps(states)
    assert result["classification"] == "PRELADDER_OBSERVATION_UNAVAILABLE"
    assert result["first_failing_step"] is None
    observed = next(row for row in result["ordered_pre_ladder_ledger"]
                    if row["step"] == missing["step"])
    assert observed["state"] == "NOT_REACHED"


def test_unknown_state_is_rejected():
    with pytest.raises((AssertionError, ValueError)):
        diag.classify_steps({LEDGER[0]["step"]: "ASSUMED_PASS"})


@pytest.mark.parametrize("changes,failed,category", [
    ({"Id": "sha256:" + "0" * 64, "Os": "windows"},
     "metadata_id_requirement", "IMAGE_ID_MISMATCH"),
    ({"Os": "windows", "Architecture": "arm64"},
     "metadata_os_requirement", "IMAGE_OS_MISMATCH"),
    ({"Architecture": "arm64", "Config": {"Volumes": {"/data": {}}}},
     "metadata_arch_requirement", "IMAGE_ARCH_MISMATCH"),
    ({"Config": {"Volumes": {"/data": {}}}},
     "metadata_volumes_requirement", "DECLARED_VOLUME_REJECTION"),
])
def test_metadata_predicates_short_circuit_in_frozen_order(changes, failed, category):
    states = diag.metadata_states(FROZEN_PREFIX, image_metadata(**changes))
    index = METADATA_STEPS.index(failed)
    assert list(states) == list(METADATA_STEPS[:index + 1])
    assert all(value["state"] == "PASS" for value in list(states.values())[:-1])
    assert states[failed]["state"] == "FAIL"
    result, rows = metadata_rows(states)
    assert result["first_failing_step"]["step"] == failed
    assert result["classification"] == category
    assert all(rows[name]["state"] == "NOT_REACHED" for name in METADATA_STEPS[index + 1:])


def test_empty_prefix_stops_before_any_metadata_access():
    class MustNotBeRead:
        def get(self, *args):
            raise AssertionError("metadata accessed after empty prefix rejection")

    states = diag.metadata_states((), MustNotBeRead())
    assert list(states) == ["metadata_prefix_requirement"]
    assert states["metadata_prefix_requirement"]["state"] == "FAIL"
    result, rows = metadata_rows(states)
    assert result["classification"] == "DOCKER_PREFIX_UNAVAILABLE"
    assert all(rows[name]["state"] == "NOT_REACHED" for name in METADATA_STEPS[1:])


@pytest.mark.parametrize("metadata", [[], None, 0, True, "json scalar"])
def test_metadata_access_error_occurs_at_id_without_invented_type_gate(metadata):
    states = diag.metadata_states(FROZEN_PREFIX, metadata)
    assert list(states) == list(METADATA_STEPS[:2])
    assert states["metadata_prefix_requirement"]["state"] == "PASS"
    failure = states["metadata_id_requirement"]
    assert failure["state"] == "FAIL"
    assert failure["error"].startswith("AttributeError:")
    result, rows = metadata_rows(states)
    assert result["classification"] == "IMAGE_METADATA_ACCESS_FAILURE"
    assert result["first_failing_step"]["step"] == "metadata_id_requirement"
    assert all(rows[name]["state"] == "NOT_REACHED" for name in METADATA_STEPS[2:])


@pytest.mark.parametrize("config", [None, [], 0, False, "json scalar"])
def test_config_access_error_occurs_only_after_id_os_and_arch_pass(config):
    states = diag.metadata_states(FROZEN_PREFIX, image_metadata(Config=config))
    assert list(states) == list(METADATA_STEPS)
    assert all(states[name]["state"] == "PASS" for name in METADATA_STEPS[:-1])
    failure = states["metadata_volumes_requirement"]
    assert failure["state"] == "FAIL"
    assert failure["error"].startswith("AttributeError:")
    result, _ = metadata_rows(states)
    assert result["classification"] == "IMAGE_METADATA_ACCESS_FAILURE"


@pytest.mark.parametrize("volumes", [None, {}, [], False, 0, ""])
def test_falsey_declared_volumes_pass_the_actual_owner_predicate(volumes):
    states = diag.metadata_states(FROZEN_PREFIX, image_metadata(Config={"Volumes": volumes}))
    assert list(states) == list(METADATA_STEPS)
    assert all(value["state"] == "PASS" for value in states.values())


@pytest.mark.parametrize("remove", ["Config", "Volumes"])
def test_missing_config_or_volumes_pass(remove):
    metadata = image_metadata()
    if remove == "Config":
        metadata.pop("Config")
    states = diag.metadata_states(FROZEN_PREFIX, metadata)
    assert all(value["state"] == "PASS" for value in states.values())


def test_mapping_access_is_required_without_requiring_exact_dict_type():
    class GetReceiver:
        def __init__(self, values):
            self.values = values

        def get(self, key, default=None):
            return self.values.get(key, default)

    metadata = GetReceiver(image_metadata(Config=GetReceiver({})))
    states = diag.metadata_states(FROZEN_PREFIX, metadata)
    assert all(value["state"] == "PASS" for value in states.values())
    assert [row["step"] for row in diag.static_ledger()
            if row["step"].startswith("metadata_")] == list(METADATA_STEPS)


def test_source_hashes_and_static_rows_reference_exact_frozen_functions():
    assert diag.check_sources() == diag.SOURCE_HASHES
    functions = {}
    for relative in diag.SOURCE_HASHES:
        text = (diag.ROOT / relative).read_text(encoding="utf-8")
        functions[relative] = {
            node.name: node for node in ast.parse(text).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    rows = diag.static_ledger()
    assert [row["order"] for row in rows] == list(range(1, len(rows) + 1))
    assert len({row["step"] for row in rows}) == len(rows)
    for row in rows:
        node = functions[row["source"]][row["function"]]
        assert node.lineno <= row["line"] <= node.end_lineno
        assert row["creates_container"] is False
        assert row["input"] and row["possible_exception_status"] and row["failure_category"]


def test_source_order_matches_prefix_policy_image_workspace_socket_invoke():
    names = [row["step"] for row in diag.static_ledger()]
    anchors = [
        "report_initialization", "docker_binary_endpoint_lookup",
        "private_config_path_construction", "docker_prefix_return",
        "policy_file_read", "exact_image_control", "image_output_parse",
        *METADATA_STEPS, "temporary_workspace_create", "workspace_path_construction",
        "policy_workspace_write", "sentinel_workspace_write", "host_tcp_bind",
        "host_tcp_listen", "host_port_read", "host_udp_bind", "ladder_first_mode",
        "invoke_mode_requirement", "invoke_fixed_source_selection",
        "invoke_fixed_command_construction", "invoke_container_name_construction",
        "invoke_capture_initialization", "first_create_argv_construction",
    ]
    indices = [names.index(name) for name in anchors]
    assert indices == sorted(indices)
    text = (diag.ROOT / "core/thread_compatible_runtime_sandbox.py").read_text(encoding="utf-8")
    invoke = next(node for node in ast.parse(text).body
                  if isinstance(node, ast.FunctionDef) and node.name == "invoke")
    creates = [node for node in ast.walk(invoke) if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Name) and node.func.id == "ctl"
               and node.args and isinstance(node.args[0], ast.Constant)
               and node.args[0].value == "create"]
    assert len(creates) == 1 and creates[0].lineno == 266


def test_control_write_close_and_poll_rows_name_the_actual_operations():
    text = (diag.ROOT / "core/candidate_runtime_sandbox.py").read_text(encoding="utf-8")
    node = next(node for node in ast.parse(text).body
                if isinstance(node, ast.FunctionDef) and node.name == "_bounded_process")
    calls = {ast.unparse(call.func): call.lineno for call in ast.walk(node)
             if isinstance(call, ast.Call)
             and ast.unparse(call.func) in (
                 "process.stdin.write", "process.stdin.close", "process.poll")}
    rows = {row["step"]: row for row in diag.static_ledger()}
    assert rows["image_control_stdin_write"]["line"] == calls["process.stdin.write"]
    assert rows["image_control_stdin_close"]["line"] == calls["process.stdin.close"]
    assert rows["image_control_process_completion"]["line"] == calls["process.poll"]


@pytest.mark.parametrize("hook", ["sys_trace", "sys_profile", "thread_trace", "thread_profile"])
def test_observer_rejects_preexisting_instrumentation_without_changing_it(hook):
    setters = {"sys_trace": sys.settrace, "sys_profile": sys.setprofile,
               "thread_trace": threading.settrace, "thread_profile": threading.setprofile}
    before = diag.instrumentation()
    callback = lambda *args: None
    setter = setters[hook]
    try:
        setter(callback)
        occupied = diag.instrumentation()
        with pytest.raises(diag.ObservationUnavailable, match="instrumentation already owned"):
            with diag.Observer():
                raise AssertionError("observer accepted occupied instrumentation")
        assert diag.instrumentation() == occupied
    finally:
        setter(before[hook])
    assert diag.instrumentation() == before


def test_observer_rejects_an_owned_monitoring_slot():
    if not hasattr(sys, "monitoring"):
        pytest.skip("runtime does not provide sys.monitoring")
    before = diag.instrumentation()
    slot = next((i for i in range(6) if sys.monitoring.get_tool(i) is None), None)
    assert slot is not None, "no free monitoring slot for pure observer test"
    try:
        sys.monitoring.use_tool_id(slot, "sandbox2-preladder-pure-test")
        occupied = diag.instrumentation()
        with pytest.raises(diag.ObservationUnavailable, match="instrumentation already owned"):
            with diag.Observer():
                raise AssertionError("observer accepted owned monitoring slot")
        assert diag.instrumentation() == occupied
    finally:
        sys.monitoring.free_tool_id(slot)
    assert diag.instrumentation() == before


@pytest.mark.parametrize("complete", [False, True])
def test_observer_retains_exact_original_fixture_pair_and_restores_hooks(complete):
    before_hooks = diag.instrumentation()
    assert all(value is None for value in before_hooks.values()), "observer requires unowned instrumentation"
    before_owner = diag.owner_snapshot()
    fixture = {
        "status": diag.owner.COMPLETE if complete else diag.owner.UNRESOLVED,
        "stages": [{"mode": mode, "verdict": diag.owner.PASSED}
                   for mode in diag.owner.LADDER] if complete else [],
        "cleanup_verified": complete,
    }
    observer = diag.Observer()
    with observer:
        pair = diag.owner._evidence_pair(fixture)
        assert observer.original_pair is pair
        descriptor, receipt = pair
        assert observer.original_pair[0] is descriptor
        assert observer.original_pair[1] is receipt
    assert observer.restored is True
    assert diag.instrumentation() == before_hooks
    facts = diag.original_pair_facts(pair)
    assert facts["original_descriptor_object_id"] == id(descriptor)
    assert facts["original_receipt_object_id"] == id(receipt)
    assert facts["HMAC_results"] == {"descriptor": True, "receipt": True}
    assert facts["semantic_eligibility"] is complete
    assert "_signature" not in facts["descriptor"] and "_signature" not in facts["receipt"]
    assert observer.original_report is None
    assert observer.controls == [] and observer.forbidden_calls == []
    assert observer.first_mode is None and observer.create_attempted is False
    assert before_owner == diag.owner_snapshot()


def test_observer_restores_hooks_and_does_not_swallow_body_exception():
    before_hooks = diag.instrumentation()
    assert all(value is None for value in before_hooks.values()), "observer requires unowned instrumentation"
    before_owner = diag.owner_snapshot()
    observer = diag.Observer()
    failure = RuntimeError("fixture error must escape the observer")
    with pytest.raises(RuntimeError) as caught:
        with observer:
            raise failure
    assert caught.value is failure
    assert observer.restored is True
    assert diag.instrumentation() == before_hooks
    assert diag.owner_snapshot() == before_owner
    assert observer.controls == []
