"""Admission is pure, atomic, exact, and fail-closed on frozen runtime authority."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core import behavioral_execution_admission as owner
from core import behavioral_evidence_execution_plan as planner
from core import read_only_reflection as reflection
from scripts.replay_patch_candidate_behavior_exec_admit1 import (
    build, lineage, no_admission_effects as no_execution_planning_effects, validate,
)
from scripts.replay_patch_candidate_behavior_exec_plan1 import (
    build as build_plan, direct_only_planning_fixture,
    planning_fixture,
)
from scripts.replay_patch_candidate_materialize1 import SCENARIOS
from scripts.replay_oop_intent_detect2 import BANK


AUTHORITY_FALSE = (
    "execution_authorized", "java_execution_authorized", "reflection_authorized",
    "console_authorized", "diagnostic_harness_generation_authorized",
    "product_write_authority", "repository_write_authority", "test_write_authority",
    "reflection_write_authority", "write_authority", "apply_authority", "network_authorized",
)
CAPABLE_PURPOSES = {"wrong_credential_transfer", "successful_transfer", "unsuccessful_debit"}
INTEREST_PURPOSES = {"wrong_credential_interest", "savings_interest"}


@pytest.fixture(scope="module")
def cases():
    class Cases(dict):
        def __missing__(self, name):
            fixture = planning_fixture(name)
            with no_execution_planning_effects():
                plan = build_plan(fixture)
                admission = build(fixture, plan)
            self[name] = fixture, plan, admission
            return self[name]
    return Cases()


@pytest.fixture(scope="module")
def compatibility(cases):
    return cases["preserve_base_compatibility"]


def scenario_rows(admission):
    return {row.scenario_id: row for row in (*admission.admitted_scenarios, *admission.blocked_scenarios)}


def _rehashed(payload):
    result = deepcopy(payload)
    result.pop("admission_fingerprint", None)
    result["admission_fingerprint"] = sha256(json.dumps(result, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return result


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_layout_classifies_every_exact_scenario_without_frozen_authority(cases, name):
    fixture, plan, admission = cases[name]
    rows = scenario_rows(admission)
    assert set(rows) == {s.scenario_id for s in plan.scenarios}
    assert not admission.admitted_scenarios
    assert len(admission.blocked_scenarios) == 5
    assert admission.execution_plan_fingerprint == plan.fingerprint
    assert admission.behavioral_spec_fingerprint == fixture[-1].fingerprint
    assert admission.compile_receipt_fingerprint == fixture[4].fingerprint
    assert admission.materialization_fingerprint == fixture[3].fingerprint
    assert admission.candidate_fingerprint == fixture[2].fingerprint
    for scenario in plan.scenarios:
        row = rows[scenario.scenario_id]
        assert row.scenario == scenario
        assert row.scenario_eligible_for_diagnostic_execution is False
        if scenario.purpose in CAPABLE_PURPOSES:
            assert row.capability_eligible is True
            assert row.status == "blocked_authority"
            assert row.reasons == ("diagnostic_execution_authority_missing",)
        else:
            assert scenario.purpose in INTEREST_PURPOSES
            assert row.capability_eligible is False
            assert row.status == "blocked_missing_capability"
            assert "deterministic_console_input" in row.reasons
    assert set(admission.capability_eligible_scenario_ids) == {s.scenario_id for s in plan.scenarios
        if s.purpose in CAPABLE_PURPOSES}
    with no_execution_planning_effects():
        assert validate(admission.as_dict(), fixture, plan) == admission


def test_exact_future_reflection_requests_preserve_minimal_observations(compatibility):
    fixture, plan, admission = compatibility
    rows = scenario_rows(admission)
    with no_execution_planning_effects():
        for scenario in plan.scenarios:
            row = rows[scenario.scenario_id]
            expected = tuple(reflection.build_read_only_reflection_request(plan,
                scenario_id=scenario.scenario_id, observation_id=o.observation_id,
                **lineage(fixture)) for o in scenario.observations
                if o.mechanism == "read_only_reflection" and row.capability_eligible)
            assert row.reflection_requests == expected
            assert tuple(r.fingerprint for r in row.reflection_requests) == tuple(r.fingerprint for r in expected)
            for request in row.reflection_requests:
                assert request.target.name in {"balance", "savingBalance"}
                assert request.operation == "read_exact_bound_field"
            if scenario.purpose == "unsuccessful_debit":
                assert {r.observation_role for r in expected} == {
                    "savings_balance_before", "savings_balance_after"}
                assert all(r.target.name == "savingBalance" for r in expected)
            elif scenario.purpose in {"wrong_credential_transfer", "successful_transfer"}:
                assert {r.observation_role for r in expected} == {
                    "ordinary_balance_before", "ordinary_balance_after",
                    "savings_balance_before", "savings_balance_after"}
    assert not admission.admitted_reflection_requests
    assert not admission.admitted_invocation_targets
    assert not admission.admitted_observation_requests


def test_wrong_credential_and_failed_debit_retain_exact_plan_fixtures(compatibility):
    _, plan, admission = compatibility
    rows = {row.scenario.purpose: row for row in admission.scenarios}
    planned = {scenario.purpose: scenario for scenario in plan.scenarios}
    wrong = rows["wrong_credential_transfer"].scenario
    assert wrong == planned["wrong_credential_transfer"]
    assert not wrong.setup_invocations
    assert wrong.isolation == "fresh_candidate_instance"
    assert [observation.mechanism for observation in wrong.observations].count("direct_return") == 1
    assert next(observation.target.declared_type for observation in wrong.observations
        if observation.mechanism == "direct_return") == "boolean"
    unsuccessful = rows["unsuccessful_debit"].scenario
    assert unsuccessful == planned["unsuccessful_debit"]
    opening = next(argument.value for argument in unsuccessful.constructor_arguments
        if argument.declared_type == "double")
    amount = next(argument for argument in unsuccessful.invocation.arguments
        if argument.declared_type == "double")
    assert amount.value > opening
    assert amount.provenance == "implementation_fixture" and amount.evidence_ref
    assert all(observation.subject == "SavingAccount::savingBalance"
        for observation in unsuccessful.observations if observation.moment in {"before", "after"})
    assert all(rows[purpose].scenario == planned[purpose] for purpose in CAPABLE_PURPOSES)


def test_static_coverage_and_blocked_obligations_are_not_behavioral_failures(compatibility):
    fixture, plan, admission = compatibility
    rows = {row.obligation_id: row for row in admission.coverage}
    assert set(rows) == {o.obligation_id for o in plan.obligations}
    static_ids = set(plan.static_satisfied_obligations)
    assert static_ids == {"BANK.credential_lifecycle", "BANK.base_savings_transition"}
    for identifier, row in rows.items():
        assert not row.admitted_scenario_ids
        if identifier in static_ids:
            assert row.status == "static_not_executed"
            assert not row.blocked_scenario_ids
        else:
            assert row.blocked_scenario_ids
            assert row.status == "blocked_runtime_evidence"
    assert admission.behavior_validated is False
    assert admission.execution_completed is False


def test_absent_reflection_blocks_whole_state_scenarios_without_getter_fallback(compatibility):
    fixture, plan, _ = compatibility
    with no_execution_planning_effects():
        admission = build(fixture, plan, reflection_descriptor=None)
        assert validate(admission, fixture, plan, reflection_descriptor=None) == admission
    assert not admission.admitted_scenarios and not admission.capability_eligible_scenario_ids
    assert len(admission.blocked_scenarios) == len(plan.scenarios)
    assert all(row.status == "blocked_missing_capability" for row in admission.blocked_scenarios)
    assert all("read_only_reflection" in row.reasons for row in admission.blocked_scenarios)
    assert all(not row.scenario_eligible_for_diagnostic_execution for row in admission.blocked_scenarios)
    assert "getter" not in admission.to_json().lower()


@pytest.mark.parametrize("field,value", (("mutation", True), ("enumeration", True),
    ("method_invocation", True), ("execution_authorized", True),
    ("availability", "execution_already_authorized"), ("operation", "write_field")))
def test_forged_typed_reflection_descriptors_are_rejected(compatibility, field, value):
    fixture, plan, _ = compatibility
    forged = deepcopy(reflection.get_read_only_reflection_capability_descriptor())
    object.__setattr__(forged, field, value)
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        build(fixture, plan, reflection_descriptor=forged)
    assert rejected.value.code in {"admission_invalid", "admission_authority_escalation",
        "admission_invalid"}


def test_descriptor_json_is_not_trusted_capability_authority(compatibility):
    fixture, plan, _ = compatibility
    descriptor = reflection.get_read_only_reflection_capability_descriptor()
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        build(fixture, plan, reflection_descriptor=descriptor.as_dict())
    assert rejected.value.code == "admission_invalid"


@pytest.mark.parametrize("field", AUTHORITY_FALSE)
def test_authority_escalation_is_rejected_recursively(compatibility, field):
    fixture, plan, admission = compatibility
    for nested in (False, True):
        payload = admission.as_dict()
        (payload["blocked_scenarios"][0] if nested else payload)[field] = True
        with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
            validate(_rehashed(payload), fixture, plan)
        assert rejected.value.code == "admission_authority_escalation"


@pytest.mark.parametrize("field", ("behavioral_execution_admitted", "execution_completed",
    "behavior_validated", "correctness_proven", "arbitrary_shell_authority",
    "candidate_revision_authority", "scenario_eligible_for_diagnostic_execution",
    "diagnostic_execution_permitted"))
def test_execution_eligibility_and_operational_grants_cannot_be_caller_authored(compatibility, field):
    fixture, plan, admission = compatibility
    payload = admission.as_dict()
    payload["blocked_scenarios"][0][field] = True
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        validate(_rehashed(payload), fixture, plan)
    assert rejected.value.code == "admission_authority_escalation"


@pytest.mark.parametrize("field,value", (
    ("shell_command", "java DiagnosticHarness"), ("java_command", ["java", "SavingAccount"]),
    ("javac_command", ["javac", "DiagnosticHarness.java"]), ("command", "cmd.exe"),
    ("test_file", "SavingAccountBehaviorTest.java"), ("java_source", "class DiagnosticHarness {}"),
    ("junit_source", "class SavingAccountBehaviorTest {}"), ("getDeclaredFields", True),
))
def test_no_command_harness_test_or_arbitrary_reflection_surface(compatibility, field, value):
    fixture, plan, admission = compatibility
    for nested in (False, True):
        payload = admission.as_dict()
        (payload["blocked_scenarios"][0] if nested else payload)[field] = value
        with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
            validate(_rehashed(payload), fixture, plan)
        assert rejected.value.code in {"admission_invalid", "admission_authority_escalation"}


@pytest.mark.parametrize("part", ("compile", "materialized", "candidate", "scope", "plan", "source", "specification", "execution_plan"))
def test_parent_lineage_changes_make_admission_stale(cases, compatibility, part):
    fixture, plan, admission = compatibility
    other_fixture, other_plan, _ = cases["nested"]
    changes = {}
    if part == "compile":
        changes["compile_receipt"] = other_fixture[4]
    elif part == "materialized":
        changes["materialized"] = other_fixture[3]
    elif part == "candidate":
        changes["candidate"] = other_fixture[2]
    elif part == "scope":
        changes["admitted_scope"] = other_fixture[0]
    elif part == "plan":
        changes["plan"] = other_fixture[1]["plan"]
    elif part == "source":
        changes["current_source"] = fixture[1]["current_source"] + b"\n// stale"
    elif part == "specification":
        changes["specification"] = other_fixture[-1]
    else:
        plan = other_plan
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        validate(admission, fixture, plan, **changes)
    assert rejected.value.code == "admission_stale"


def test_capability_change_invalidates_historical_admission_without_mutation(compatibility):
    fixture, plan, admission = compatibility
    before = admission.to_json()
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        validate(admission, fixture, plan, reflection_descriptor=None)
    assert rejected.value.code == "admission_stale"
    assert admission.to_json() == before


def test_plan_and_descriptor_reconstruction_cannot_be_skipped(compatibility):
    fixture, plan, _ = compatibility
    with no_execution_planning_effects(), patch.object(planner,
            "validate_behavioral_evidence_execution_plan", wraps=planner.validate_behavioral_evidence_execution_plan) as gate:
        build(fixture, plan)
    assert gate.call_count >= 1
    with no_execution_planning_effects(), patch.object(reflection,
            "validate_read_only_reflection_capability_descriptor", wraps=reflection.validate_read_only_reflection_capability_descriptor) as gate:
        build(fixture, plan)
    assert gate.call_count >= 1


def test_immutable_idempotent_timings_are_external(compatibility):
    fixture, plan, admission = compatibility
    samples = [{}, {}]
    with no_execution_planning_effects():
        repeated = [build(fixture, plan, timings=sample) for sample in samples]
        assert validate(admission.as_dict(), fixture, plan) == admission
    assert repeated[0] == repeated[1] == admission
    assert repeated[0].fingerprint == repeated[1].fingerprint == admission.fingerprint
    assert json.loads(admission.to_json()) == admission.as_dict()
    assert all(set(sample) == set(owner.TIMING_FIELDS) for sample in samples)
    assert all(type(value) is float and value >= 0 for sample in samples for value in sample.values())
    assert "timings" not in admission.as_dict()
    with pytest.raises(FrozenInstanceError):
        admission.status = "admitted"
    with pytest.raises(FrozenInstanceError):
        admission.blocked_scenarios[0].status = "admitted"
    with pytest.raises(owner.BehavioralExecutionAdmissionError):
        replace(admission, blocked_scenarios=list(admission.blocked_scenarios))


@pytest.mark.parametrize("transfer_name,extra_transfer,count", (
    ("transferToSavings", False, 5), ("moveToSavings", False, 5), ("transferToSavings", True, 8),
))
def test_direct_only_capability_ready_fixture_cannot_invent_runtime_authority(transfer_name, extra_transfer, count):
    fixture = direct_only_planning_fixture(transfer_name=transfer_name, extra_transfer=extra_transfer)
    with no_execution_planning_effects():
        plan = build_plan(fixture)
        admission = build(fixture, plan, reflection_descriptor=None)
        assert validate(admission, fixture, plan, reflection_descriptor=None) == admission
    assert len(admission.blocked_scenarios) == len(admission.capability_eligible_scenario_ids) == count
    assert not admission.admitted_scenarios
    assert all(row.capability_eligible and row.status == "blocked_authority"
        for row in admission.blocked_scenarios)
    assert all(row.reasons == ("diagnostic_execution_authority_missing",)
        and not row.reflection_requests for row in admission.blocked_scenarios)
    assert all(s.invocation.console_input is None for s in plan.scenarios)
    assert all("read_only_reflection" not in s.required_capabilities for s in plan.scenarios)
    assert {s.invocation.target.name for s in plan.scenarios if s.purpose in CAPABLE_PURPOSES} == (
        {transfer_name, "moveToSavings"} if extra_transfer else {transfer_name})
    descriptors = {row.capability: row for row in admission.capability_descriptors}
    query_targets = {observation.target for scenario in plan.scenarios
        for observation in scenario.observations if observation.mechanism == "existing_exact_state_query"}
    field_targets = {observation.target for scenario in plan.scenarios
        for observation in scenario.observations if observation.mechanism == "direct_state_access"}
    assert query_targets and field_targets
    package = descriptors["existing_package_access"]
    assert package.operation == "access_exact_plan_bound_surface"
    assert query_targets <= set(package.exact_targets)
    package_state = {observation.target for scenario in plan.scenarios for observation in scenario.observations
        if "existing_package_access" in observation.required_capabilities}
    assert package_state <= set(package.exact_targets)
    assert set(descriptors["direct_state_observation"].exact_targets) == query_targets | field_targets


def test_unproved_constructor_setup_remains_a_missing_capability():
    fixture = planning_fixture(source=BANK.replace("this.balance = opening;", "this.balance = opening + 2;"))
    with no_execution_planning_effects():
        plan = build_plan(fixture)
        admission = build(fixture, plan)
        assert validate(admission, fixture, plan) == admission
    assert not admission.capability_eligible_scenario_ids and not admission.admitted_scenarios
    assert all(row.status == "blocked_missing_capability" for row in admission.blocked_scenarios)


def test_zero_effects_and_no_execution_or_write_grants(compatibility):
    _, _, admission = compatibility
    payload = admission.as_dict()
    assert all(payload[key] is False for key in AUTHORITY_FALSE)
    assert payload["scope_authority"] == "diagnostic_behavioral_execution_only"
    for key in ("model_calls", "author_calls", "repository_traversals", "source_mutation",
            "test_generation_count", "java_execution_count", "javac_calls",
            "reflection_execution_count", "console_open_count", "diagnostic_harness_generation_count"):
        assert payload[key] == 0
    assert payload["runtime_executor_status"] == "runtime_executor_capability_missing"
    forbidden = {"java_source", "test_source", "junit_source", "command", "commands",
        "shell_command", "java_command", "javac_command", "source_text", "assertion_code"}
    def inspect(value):
        if isinstance(value, dict):
            assert not forbidden & value.keys()
            for item in value.values():
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)
    inspect(payload)


def test_admission_never_generates_source_or_issues_actual_read_receipts(compatibility):
    fixture, plan, admission = compatibility
    with no_execution_planning_effects(), patch(
            "core.read_only_reflection_java.render_read_only_reflection_adapter",
            side_effect=AssertionError("admission attempted reflection source generation")), patch.object(
            reflection, "_issue_adapter_observation",
            side_effect=AssertionError("admission attempted an actual-read receipt")):
        rebuilt = build(fixture, plan)
        assert validate(rebuilt, fixture, plan) == admission


def test_direct_capabilities_bind_only_existing_exact_plan_surfaces(compatibility):
    _, plan, admission = compatibility
    descriptors = {row.capability: row for row in admission.capability_descriptors}
    invocations = {target for scenario in plan.scenarios for target in (
        scenario.constructor, scenario.invocation.target,
        *(call.target for call in scenario.setup_invocations))}
    returns = {observation.target for scenario in plan.scenarios
        for observation in scenario.observations if observation.mechanism == "direct_return"}
    assert set(descriptors["direct_public_invocation"].exact_targets) == invocations
    assert set(descriptors["direct_return_observation"].exact_targets) == returns
    assert descriptors["direct_public_invocation"].operation == "invoke_exact_plan_bound_surface"
    assert descriptors["direct_return_observation"].operation == "capture_exact_direct_return"
    assert descriptors["read_only_reflection"].reflection_descriptor_fingerprint == (
        reflection.get_read_only_reflection_capability_descriptor().fingerprint)
    assert descriptors["deterministic_console_input"].availability == "unavailable"
    assert not descriptors["deterministic_console_input"].exact_targets
    known_fingerprints = {row.fingerprint for row in descriptors.values()}
    assert all(set(row.capability_descriptor_fingerprints) <= known_fingerprints
        for row in admission.scenarios)
    assert not admission.admitted_capability_descriptors


def test_frozen_evidence_need_binds_question_without_runtime_grant(compatibility):
    fixture, _, admission = compatibility
    authority = admission.evidence_authority
    assert authority.source == "PREFLIGHT.REQUEST.1/ACQUIRE.1"
    assert authority.diagnostic_kind == "runtime_evidence"
    assert authority.status == "diagnostic_execution_authority_missing"
    assert authority.diagnostic_execution_permitted is False
    assert authority.evidence_requirement_fingerprint == admission.evidence_requirement_fingerprint
    assert len(authority.policy_fingerprint) == 64
    assert authority.behavioral_need_fingerprints
    proposed = [need.proposed_test_file for need in fixture[0].validation_evidence_needs
        if need.proposed_test_file]
    assert proposed == ["SavingAccountBehaviorTest.java"]
    assert all(not need.test_write_authority for need in fixture[0].validation_evidence_needs)
    assert admission.test_file_handling == "proposed_test_file_only"
    assert all(target.path not in proposed for target in admission.admitted_invocation_targets)


def test_runtime_isolation_is_required_without_claiming_implemented_enforcement(compatibility):
    _, _, admission = compatibility
    assert admission.process_local_authenticated_reflection_receipt_required is True
    for row in admission.scenarios:
        isolation = row.isolation_requirements
        assert all(getattr(isolation, key) is True for key in (
            "ephemeral_workspace_required", "exact_virtual_candidate_bytes_required",
            "fresh_candidate_instance_required", "repository_source_write_forbidden",
            "child_process_cleanup_required", "arbitrary_command_surface_forbidden",
            "persistent_diagnostic_artifacts_forbidden"))
        assert isolation.wall_clock_timeout_seconds > 0
        assert isolation.stdout_limit_bytes > 0 and isolation.stderr_limit_bytes > 0
        assert isolation.network_capability is False
        assert isolation.filesystem_persistence_authority is False
        assert isolation.minimum_runtime_boundary_enforced is False
        assert isolation.hard_network_isolation_available is False
        assert isolation.hard_filesystem_isolation_available is False
        assert isolation.executor_status == "runtime_executor_capability_missing"
        assert row.process_local_authenticated_reflection_receipt_required is True
        assert row.candidate_runtime_receipt_issuance_available is False


@pytest.mark.parametrize("part", ("reflection_request", "extra_observation", "extra_method",
    "fixture_value", "fixture_provenance", "admitted_target", "missing_scenario", "coverage"))
def test_rehashed_payload_cannot_expand_exact_scope_or_reduce_frozen_oracles(compatibility, part):
    fixture, plan, admission = compatibility
    payload = admission.as_dict()
    row = next(row for row in payload["blocked_scenarios"]
        if row["scenario"]["purpose"] == "successful_transfer")
    if part == "reflection_request":
        row["reflection_requests"][0]["target"]["name"] = "password"
    elif part == "extra_observation":
        extra = deepcopy(row["scenario"]["observations"][0])
        extra["observation_id"] = "unplanned_password_observation"
        extra["target"]["name"] = "password"
        row["scenario"]["observations"].append(extra)
    elif part == "extra_method":
        extra = deepcopy(row["scenario"]["invocation"])
        extra["target"]["name"] = "unplannedProductMethod"
        row["scenario"]["setup_invocations"].append(extra)
    elif part in {"fixture_value", "fixture_provenance"}:
        argument = next(arg for arg in row["scenario"]["invocation"]["arguments"]
            if arg["declared_type"] == "double")
        argument["value" if part == "fixture_value" else "provenance"] = (
            123456.0 if part == "fixture_value" else "implementation_contract")
    elif part == "admitted_target":
        payload["admitted_invocation_targets"].append(deepcopy(row["scenario"]["invocation"]["target"]))
    elif part == "missing_scenario":
        payload["blocked_scenarios"].remove(row)
    else:
        payload["coverage"] = payload["coverage"][1:]
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        validate(_rehashed(payload), fixture, plan)
    assert rejected.value.code == "admission_scope_mismatch"


def test_interest_admission_cannot_omit_console_requirement(compatibility):
    fixture, plan, admission = compatibility
    payload = admission.as_dict()
    interest = next(row for row in payload["blocked_scenarios"]
        if row["scenario"]["purpose"] == "savings_interest")
    interest["scenario"]["required_capabilities"].remove("deterministic_console_input")
    interest["capability_eligible"] = True
    interest["status"] = "admitted"
    interest["reasons"] = []
    payload["blocked_scenarios"].remove(interest)
    payload["admitted_scenarios"].append(interest)
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        validate(_rehashed(payload), fixture, plan)
    assert rejected.value.code == "admission_scope_mismatch"


def test_self_hashed_runtime_authority_label_cannot_replace_frozen_authority(compatibility):
    fixture, plan, admission = compatibility
    payload = admission.as_dict()
    payload["evidence_authority"]["source"] = "caller_claimed_human_approval"
    payload["evidence_authority"]["status"] = "execution_authorized"
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        validate(_rehashed(payload), fixture, plan)
    assert rejected.value.code == "admission_stale"


def test_dataclass_reconstruction_and_constructor_bypass_cannot_forge_selection(compatibility):
    fixture, plan, admission = compatibility
    original = next(row for row in admission.blocked_scenarios if row.capability_eligible)
    altered = replace(original, capability_eligible=False)
    forged = replace(admission, blocked_scenarios=tuple(altered if row is original else row
        for row in admission.blocked_scenarios))
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        validate(forged, fixture, plan)
    assert rejected.value.code == "admission_scope_mismatch"
    bypass = deepcopy(admission)
    object.__setattr__(bypass, "java_execution_authorized", True)
    with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
        validate(bypass, fixture, plan)
    assert rejected.value.code == "admission_authority_escalation"


def test_bookkeeping_reversal_preserves_every_frozen_prerequisite_receipt():
    from tests._patch_candidate_behavior_exec_admit1_maintenance import before_patch_candidate_behavior_exec_admit1
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tests/fixtures/patch_candidate_behavior_exec_admit1_reversal.json")
        .read_text(encoding="utf-8"))
    for record in receipt["reversals"]:
        content = (root / record["path"]).read_bytes()
        restored = before_patch_candidate_behavior_exec_admit1(record["path"], content)
        assert sha256(restored).hexdigest() == record["entry_sha256"]
        with pytest.raises(AssertionError):
            before_patch_candidate_behavior_exec_admit1(record["path"], content + b"\n")


def test_nested_immutable_authority_and_capability_records_reject_lists(compatibility):
    _, _, admission = compatibility
    for operation in (
            lambda: replace(admission.evidence_authority,
                behavioral_need_fingerprints=list(admission.evidence_authority.behavioral_need_fingerprints)),
            lambda: replace(admission.capability_descriptors[0],
                exact_targets=list(admission.capability_descriptors[0].exact_targets)),
            lambda: replace(admission.blocked_scenarios[0],
                reflection_requests=list(admission.blocked_scenarios[0].reflection_requests))):
        with no_execution_planning_effects(), pytest.raises(owner.BehavioralExecutionAdmissionError) as rejected:
            operation()
        assert rejected.value.code == "admission_invalid"
