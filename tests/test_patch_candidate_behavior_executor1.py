"""EXECUTOR.1 authenticates blocked evidence and never weakens frozen isolation.

No runnable adapter is available under the required hard filesystem/network
boundary. Therefore the explicit capability-incomplete stop condition applies,
and a whole-suite no-runtime guard proves zero effects. When isolation permits
execution, this guard must become an adapter-owned launch-count guard; it must
never accidentally suppress the capability being tested.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import behavioral_diagnostic_executor as owner
    from core import runtime_diagnostic_authorization as authorization_owner
    from core.input_understanding import understand_request
    from scripts.replay_patch_candidate_behavior_executor1 import (
        build_case, execute, execution_inputs, validate,
    )
    from tests.test_preflight_runtime1 import (
        build as build_authorization, external_reflection_parents, issue,
        rehashed, snapshot,
    )


FALSE_AUTHORITIES = (
    "product_write_authority", "repository_write_authority", "reflection_write_authority",
    "test_write_authority", "apply_authority",
)
ZERO_EFFECTS = (
    "java_execution_count", "reflection_execution_count", "console_open_count",
    "javac_calls", "diagnostic_harness_generation_count", "test_generation_count",
    "model_calls", "author_calls", "repository_traversals", "source_mutation",
)
UNEXECUTED_TIMINGS = (
    "virtual_byte_projection_seconds", "harness_rendering_seconds", "harness_compile_seconds",
    "jvm_startup_seconds", "scenario_execution_seconds", "reflection_observations_seconds",
    "cleanup_seconds",
)


@pytest.fixture(scope="module", autouse=True)
def deny_entire_focused_suite():
    with no_runtime_effects() as evidence:
        yield evidence


@pytest.fixture(scope="module")
def cases(deny_entire_focused_suite):
    class Cases(dict):
        def __missing__(self, name):
            self[name] = build_case(name)
            return self[name]
    return Cases()


@pytest.fixture(scope="module")
def bank(cases):
    return cases["preserve_base_compatibility"]


@pytest.fixture(scope="module")
def authorized(bank):
    source = issue(bank, fixture_id="synthetic.EXECUTOR.1.focused")
    authorization = build_authorization(bank, source=source)
    selected = next(s for s in bank[1].scenarios if s.purpose == "successful_transfer")
    return source, authorization, selected


@pytest.fixture(scope="module")
def receipt(bank, authorized):
    source, authorization, selected = authorized
    return execute(authorization, bank, selected.scenario_id, source=source)


def assert_no_execution(receipt):
    payload = receipt.as_dict()
    assert receipt.execution_completed is False
    assert payload["authority"] == "diagnostic_runtime_evidence_only"
    assert all(payload[field] is False for field in FALSE_AUTHORITIES)
    assert all(payload[field] == 0 for field in ZERO_EFFECTS)
    assert receipt.harness_sha256 == ""
    assert receipt.constructor_result is None
    assert receipt.setup_invocation_results == ()
    assert receipt.action_invocation_result is None
    assert receipt.direct_return_observations == ()
    assert receipt.reflection_observations == ()
    assert all(key not in payload for key in (
        "behavior_passed", "correctness_proven", "feature_correct", "oracle_passed"))


def test_descriptor_truthfully_declares_required_isolation_unavailable():
    descriptor = owner.get_bounded_java_diagnostic_executor_descriptor()
    payload = descriptor.as_dict()
    assert payload["capability"] == "bounded_java_diagnostic_executor"
    assert payload["runtime_executor_available"] is False
    assert payload["filesystem_isolation_enforced"] is False
    assert payload["network_isolation_enforced"] is False
    assert payload["console"] is False
    assert payload["arbitrary_command"] is False
    assert payload["reflection_read_only"] is True
    assert payload["repository_write_authority"] is False
    assert payload["network_authority"] is False
    assert "command" not in {field.name for field in fields(descriptor)}
    with pytest.raises(FrozenInstanceError):
        descriptor.runtime_executor_available = True


@pytest.mark.parametrize("purpose", (
    "wrong_credential_transfer", "successful_transfer", "unsuccessful_debit",
))
def test_exact_synthetic_authority_reaches_only_capability_incomplete_boundary(bank, purpose,
        deny_entire_focused_suite):
    before = snapshot(bank)
    denied_before = dict(deny_entire_focused_suite.denied_attempts)
    source = issue(bank, purposes=(purpose,), fixture_id="synthetic.EXECUTOR.1." + purpose)
    authorization = build_authorization(bank, source=source)
    selected = next(s for s in bank[1].scenarios if s.purpose == purpose)
    assert authorization.diagnostic_runtime_policy_authorized is True
    assert authorization.authorized_scenario_ids == (selected.scenario_id,)
    result = execute(authorization, bank, selected.scenario_id, source=source)
    assert result.status == "runtime_executor_capability_incomplete"
    assert result.scenario_id == selected.scenario_id
    assert_no_execution(result)
    assert validate(result, authorization, bank, selected.scenario_id, source=source) == result
    assert snapshot(bank) == before
    assert deny_entire_focused_suite.denied_attempts == denied_before


def test_authorization_gate_reconstructs_exact_fresh_parents_before_receipt(bank, authorized):
    source, authorization, selected = authorized
    with patch.object(authorization_owner, "validate_runtime_diagnostic_authorization",
            wraps=authorization_owner.validate_runtime_diagnostic_authorization) as gate:
        result = execute(authorization, bank, selected.scenario_id, source=source)
    assert gate.call_count >= 1
    assert gate.call_args.kwargs["execution_plan"] == bank[1]
    assert gate.call_args.kwargs["candidate"] == bank[0][2]
    assert gate.call_args.kwargs["authorization_source"] == source
    assert_no_execution(result)


def test_real_BANK_without_operational_runtime_authority_is_authenticated_negative(bank):
    before = snapshot(bank)
    authorization = build_authorization(bank)
    selected = next(s for s in bank[1].scenarios if s.purpose == "successful_transfer")
    result = execute(authorization, bank, selected.scenario_id)
    assert result.status == "diagnostic_execution_authority_missing"
    assert_no_execution(result)
    assert validate(result, authorization, bank, selected.scenario_id) == result
    assert snapshot(bank) == before


def test_easy_direct_only_scenario_does_not_infer_policy_authority(cases):
    case = cases["direct"]
    authorization = build_authorization(case, reflection_descriptor=None)
    selected = next(s for s in case[1].scenarios if s.purpose == "successful_transfer")
    result = execute(authorization, case, selected.scenario_id)
    assert result.status == "diagnostic_execution_authority_missing"
    assert_no_execution(result)


@pytest.mark.parametrize("purpose", ("wrong_credential_interest", "savings_interest"))
def test_synthetic_interest_authority_never_maps_console_to_stdin(bank, purpose):
    source = issue(bank, purposes=(purpose,), fixture_id="synthetic.EXECUTOR.1." + purpose)
    authorization = build_authorization(bank, source=source)
    scenario_id = authorization.authorized_scenario_ids[0]
    assert authorization.diagnostic_runtime_policy_authorized is True
    result = execute(authorization, bank, scenario_id, source=source)
    assert result.status == "runtime_executor_console_unavailable"
    assert_no_execution(result)
    assert validate(result, authorization, bank, scenario_id, source=source) == result


@pytest.mark.parametrize("kind", ("absent", "plain_dict", "wrong_type"))
def test_missing_or_caller_authored_authorization_stops_before_effects(bank, authorized, kind):
    source, authorization, selected = authorized
    forged = None if kind == "absent" else ({} if kind == "plain_dict" else object())
    with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
        execute(forged, bank, selected.scenario_id, source=source)
    assert rejected.value.code == "executor_authorization_missing"
    assert rejected.value.java_execution_count == 0


@pytest.mark.parametrize("scenario_id", ("BANK.unplanned", "BANK.*", "all scenarios", ""))
def test_unknown_or_wildcard_selection_cannot_create_authority(bank, authorized, scenario_id):
    source, authorization, _ = authorized
    with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
        execute(authorization, bank, scenario_id, source=source)
    assert rejected.value.code == "executor_authorization_missing"
    assert rejected.value.java_execution_count == 0


def test_known_but_unselected_scenario_cannot_borrow_another_scenario_grant(bank, authorized):
    source, authorization, _ = authorized
    scenario_id = next(s.scenario_id for s in bank[1].scenarios
        if s.purpose == "wrong_credential_transfer")
    result = execute(authorization, bank, scenario_id, source=source)
    assert result.status == "diagnostic_execution_authority_missing"
    assert_no_execution(result)
    assert validate(result, authorization, bank, scenario_id, source=source) == result


@pytest.mark.parametrize("part", (
    "task", "repository", "candidate", "materialization", "compile", "specification",
    "execution_plan", "source_bytes", "authorization_source", "admission",
))
def test_stale_authorization_has_zero_effects(cases, bank, authorized, part):
    source, authorization, selected = authorized
    fixture = bank[0]
    other_fixture, other_plan, other_admission = cases["nested"]
    changes = {}
    if part == "task":
        changes["task_contract"] = understand_request(fixture[1]["task_contract"].raw_request.text + "\nchanged")
    elif part == "repository":
        changes["repository_id"] = "different-" + "b" * 32
    elif part == "candidate":
        changes["candidate"] = other_fixture[2]
    elif part == "materialization":
        changes["materialized"] = other_fixture[3]
    elif part == "compile":
        changes["compile_receipt"] = other_fixture[4]
    elif part == "specification":
        changes["specification"] = other_fixture[5]
    elif part == "execution_plan":
        changes["execution_plan"] = other_plan
    elif part == "source_bytes":
        changes["current_source"] = fixture[1]["current_source"] + b"\n// stale"
    elif part == "authorization_source":
        source = issue(bank, fixture_id="synthetic.EXECUTOR.1.changed-source")
    else:
        changes["behavioral_admission"] = other_admission
    with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
        execute(authorization, bank, selected.scenario_id, source=source, **changes)
    assert rejected.value.code == "executor_authorization_missing"
    assert rejected.value.java_execution_count == 0


@pytest.mark.parametrize("part", (
    "extra_method", "extra_observation", "reflection_write", "field_enumeration",
    "private_method", "fixture_value", "omit_constructor", "extra_scenario",
))
def test_rehashed_authorization_cannot_widen_or_reduce_exact_scope(bank, authorized, part):
    source, authorization, selected = authorized
    payload = deepcopy(authorization.as_dict())
    if part == "extra_method":
        extra = deepcopy(payload["authorized_invocation_targets"][0])
        extra["name"] = "unapprovedMethod"
        payload["authorized_invocation_targets"].append(extra)
    elif part == "extra_observation":
        extra = deepcopy(payload["authorized_observation_targets"][0])
        extra["observation_id"] = "unapproved_debug_read"
        extra["target"]["name"] = "password"
        payload["authorized_observation_targets"].append(extra)
    elif part == "reflection_write":
        payload["authorized_reflection_requests"][0]["operation"] = "write_field"
    elif part == "field_enumeration":
        payload["getDeclaredFields"] = True
    elif part == "private_method":
        payload["private_method_invocation_authority"] = True
    elif part == "fixture_value":
        argument = next(a for a in payload["authorized_scenarios"][0]["invocation"]["arguments"]
            if a["declared_type"] == "double")
        argument["value"] = 123456.0
    elif part == "omit_constructor":
        payload["authorized_invocation_targets"] = [target for target in
            payload["authorized_invocation_targets"] if target["kind"] != "constructor"]
    else:
        payload["authorized_scenario_ids"].append("BANK.unapproved")
    with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
        execute(rehashed(payload), bank, selected.scenario_id, source=source)
    assert rejected.value.code == "executor_authorization_missing"
    assert rejected.value.java_execution_count == 0


@pytest.mark.parametrize("part", (
    "extra_method", "extra_observation", "reflection_write", "fixture_value",
    "missing_constructor", "network_grant", "shell_grant", "repository_write_grant",
    "field_enumeration_grant", "private_method_grant",
))
def test_rehashed_typed_forgery_reaches_fresh_validator_and_is_rejected(bank, authorized, part):
    source, authorization, selected = authorized
    forged = deepcopy(authorization)
    if part == "extra_method":
        extra = deepcopy(forged.authorized_invocation_targets[0])
        object.__setattr__(extra, "name", "unapprovedMethod")
        object.__setattr__(forged, "authorized_invocation_targets", (*forged.authorized_invocation_targets, extra))
    elif part == "extra_observation":
        extra = deepcopy(forged.authorized_observation_targets[0])
        object.__setattr__(extra, "observation_id", "unapproved_debug_read")
        object.__setattr__(extra.target, "name", "password")
        object.__setattr__(forged, "authorized_observation_targets", (*forged.authorized_observation_targets, extra))
    elif part == "reflection_write":
        object.__setattr__(forged.authorized_reflection_requests[0], "operation", "write_field")
    elif part == "fixture_value":
        argument = next(a for a in forged.authorized_scenarios[0].invocation.arguments
            if a.declared_type == "double")
        object.__setattr__(argument, "value", 123456.0)
    elif part == "missing_constructor":
        object.__setattr__(forged, "authorized_invocation_targets", tuple(target for target in
            forged.authorized_invocation_targets if target.kind != "constructor"))
    else:
        field = {"network_grant": "network_authorized", "shell_grant": "arbitrary_shell_authority",
            "repository_write_grant": "repository_write_authority",
            "field_enumeration_grant": "field_enumeration_authority",
            "private_method_grant": "private_method_invocation_authority"}[part]
        object.__setattr__(forged, field, True)
    # RuntimeDiagnosticAuthorization recomputes its public digest, so this is
    # also a correctly rehashed typed forgery rather than a malformed digest.
    assert forged.fingerprint != authorization.fingerprint
    with patch.object(authorization_owner, "validate_runtime_diagnostic_authorization",
            wraps=authorization_owner.validate_runtime_diagnostic_authorization) as gate:
        with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
            execute(forged, bank, selected.scenario_id, source=source)
    assert gate.call_count >= 1
    assert rejected.value.code == "executor_authorization_missing"
    assert rejected.value.java_execution_count == 0


@pytest.mark.parametrize("field,value", (
    ("shell_command", "cmd.exe /c arbitrary"), ("java_command", ["java", "Arbitrary"]),
    ("network_authorized", True), ("repository_write_authority", True),
    ("product_write_authority", True), ("reflection_write_authority", True),
    ("test_write_authority", True), ("apply_authority", True),
    ("java_source", "class Arbitrary {}"), ("test_file", "SavingAccountBehaviorTest.java"),
))
def test_shell_network_source_and_write_payloads_cannot_cross_gate(bank, authorized, field, value):
    source, authorization, selected = authorized
    payload = authorization.as_dict()
    payload[field] = value
    with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
        execute(rehashed(payload), bank, selected.scenario_id, source=source)
    assert rejected.value.code == "executor_authorization_missing"
    assert rejected.value.java_execution_count == 0


def test_blocked_receipt_preserves_exact_inputs_without_claiming_a_harness(bank, authorized, receipt):
    source, authorization, selected = authorized
    assert type(receipt.input_manifest) is tuple
    assert receipt.input_manifest
    for virtual in bank[0][3].virtual_files:
        assert sha256(virtual.after_bytes).hexdigest() == virtual.after_sha256
        assert virtual.after_sha256 in receipt.to_json()
    for record in (authorization, bank[1], bank[0][2], bank[0][3], bank[0][4], bank[0][5]):
        assert record.fingerprint in receipt.to_json()
    assert selected.scenario_id in receipt.to_json()
    assert source.fingerprint in authorization.to_json()
    assert_no_execution(receipt)


def test_exact_constructor_fixtures_setup_action_and_read_only_observations_are_bound(bank,
        authorized, receipt):
    _, authorization, selected = authorized
    assert receipt.constructor_target == selected.constructor
    assert receipt.constructor_arguments == selected.constructor_arguments
    assert receipt.setup_invocations == selected.setup_invocations
    assert receipt.action_invocation == selected.invocation
    assert receipt.observation_targets == selected.observations
    assert receipt.reflection_requests == tuple(request for request in
        authorization.authorized_reflection_requests if request.scenario_id == selected.scenario_id)
    assert all(request.operation == "read_exact_bound_field" for request in receipt.reflection_requests)
    assert {request.target.name for request in receipt.reflection_requests} == {"balance", "savingBalance"}
    assert receipt.workspace_created is False
    assert receipt.virtual_bytes_projected is False
    assert receipt.compiler_identity is None
    assert receipt.jvm_identity is None
    assert receipt.process_exit_status is None
    assert receipt.stdout_metadata is None
    assert receipt.stderr_metadata is None


def test_receipt_is_immutable_process_local_and_export_is_not_authenticated(bank, authorized, receipt):
    source, authorization, selected = authorized
    assert json.loads(receipt.to_json()) == receipt.as_dict()
    assert "_signature" not in receipt.as_dict()
    assert validate(receipt, authorization, bank, selected.scenario_id, source=source) == receipt
    with pytest.raises(FrozenInstanceError):
        receipt.status = "completed"
    for forged in (receipt.as_dict(), json.loads(receipt.to_json()), {}):
        with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
            validate(forged, authorization, bank, selected.scenario_id, source=source)
        assert rejected.value.code == "executor_receipt_unauthenticated"


@pytest.mark.parametrize("mutation", ("unsigned", "status", "harness", "observations", "signature"))
def test_unsigned_or_tampered_execution_receipt_never_authenticates(bank, authorized, receipt, mutation):
    source, authorization, selected = authorized
    forged = deepcopy(receipt)
    if mutation == "unsigned":
        object.__setattr__(forged, "_signature", "")
    elif mutation == "status":
        object.__setattr__(forged, "status", "execution_completed")
    elif mutation == "harness":
        object.__setattr__(forged, "harness_sha256", "a" * 64)
    elif mutation == "observations":
        object.__setattr__(forged, "direct_return_observations", (("forged_return", True),))
    else:
        object.__setattr__(forged, "_signature", "a" * 64)
    with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
        validate(forged, authorization, bank, selected.scenario_id, source=source)
    assert rejected.value.code in {"executor_receipt_unauthenticated", "executor_receipt_invalid"}
    assert rejected.value.java_execution_count == 0


def test_receipt_validator_freshly_reconstructs_authorization_and_rejects_stale_source(bank,
        authorized, receipt):
    source, authorization, selected = authorized
    with patch.object(authorization_owner, "validate_runtime_diagnostic_authorization",
            wraps=authorization_owner.validate_runtime_diagnostic_authorization) as gate:
        assert validate(receipt, authorization, bank, selected.scenario_id, source=source) == receipt
    assert gate.call_count >= 1
    with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
        validate(receipt, authorization, bank, selected.scenario_id, source=source,
            current_source=bank[0][1]["current_source"] + b"\n// changed")
    assert rejected.value.code in {"executor_authorization_missing", "executor_receipt_stale"}
    assert rejected.value.java_execution_count == 0


def test_receipt_cannot_rebind_to_another_valid_scenario(bank, authorized, receipt):
    source, authorization, _ = authorized
    other_id = next(s.scenario_id for s in bank[1].scenarios
        if s.purpose == "wrong_credential_transfer")
    with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
        validate(receipt, authorization, bank, other_id, source=source)
    assert rejected.value.code == "executor_receipt_stale"
    assert rejected.value.java_execution_count == 0


@pytest.mark.parametrize("status", (
    "harness_compile_failed", "runtime_launch_failed", "timeout", "output_overflow",
    "observation_failed", "authorized_action_threw", "execution_completed",
))
def test_unexecuted_runtime_outcomes_cannot_be_fabricated(receipt, status):
    # The mandatory isolation stop precedes these stages. Reporting a timeout,
    # overflow, compile/launch failure or candidate exception would invent facts.
    with pytest.raises(owner.BehavioralDiagnosticExecutionError) as rejected:
        replace(receipt, status=status)
    assert rejected.value.code == "executor_receipt_invalid"
    assert rejected.value.java_execution_count == 0


def test_idempotent_semantic_identity_excludes_timings(bank, authorized):
    source, authorization, selected = authorized
    measurements = [{}, {}]
    receipts = [execute(authorization, bank, selected.scenario_id, source=source,
        timings=sample) for sample in measurements]
    assert receipts[0].fingerprint == receipts[1].fingerprint
    assert receipts[0].as_dict() == receipts[1].as_dict()
    assert "timings" not in receipts[0].as_dict()
    assert all(set(sample) == set(owner.TIMING_FIELDS) for sample in measurements)
    assert all(type(value) is float and value >= 0 for sample in measurements for value in sample.values())
    assert all(sample[key] == 0.0 for sample in measurements for key in UNEXECUTED_TIMINGS)


def test_unavailable_boundary_has_no_renderer_launcher_or_runtime_receipt_issuance():
    exported = {name for name in dir(owner) if not name.startswith("_")}
    assert not any(name.startswith(("render_", "run_java", "launch_", "compile_")) for name in exported)
    assert not {"subprocess", "Popen", "tempfile", "socket", "os"} & exported
    assert not {"issue_reflection_observation", "write_field", "enumerate_fields"} & exported


def test_entire_fixture_guard_prevents_runtime_generation_network_traversal_and_writes():
    import os
    import socket
    import subprocess
    from core import read_only_reflection
    from core import read_only_reflection_java
    with no_runtime_effects() as guard:
        operations = (
            lambda: subprocess.run(["java", "NeverLaunched"]),
            lambda: os.system("javac NeverCompiled.java"),
            lambda: socket.create_connection(("127.0.0.1", 1)),
            lambda: input("No console"),
            lambda: read_only_reflection_java.render_read_only_reflection_adapter(None),
            lambda: read_only_reflection._issue_adapter_observation(None),
            lambda: os.listdir("."),
            lambda: Path("NeverCreated.java").write_text("class NeverCreated {}"),
        )
        for operation in operations:
            with pytest.raises(AssertionError, match="PREFLIGHT.RUNTIME.1 effect denied"):
                operation()
        assert len(guard.denied_attempts) == len(operations)


def test_bookkeeping_reversal_preserves_exact_frozen_receipts():
    from tests._patch_candidate_behavior_executor1_maintenance import before_patch_candidate_behavior_executor1
    root = Path(__file__).resolve().parents[1]
    reversal = json.loads((root / "tests/fixtures/patch_candidate_behavior_executor1_reversal.json").read_text(encoding="utf-8"))
    assert len(reversal["reversals"]) == 4
    for record in reversal["reversals"]:
        content = (root / record["path"]).read_bytes()
        assert sha256(before_patch_candidate_behavior_executor1(record["path"], content)).hexdigest() == record["entry_sha256"]
        with pytest.raises(AssertionError):
            before_patch_candidate_behavior_executor1(record["path"], content + b"\n")
