"""Typed execution routes only: no Java, reflection, console or source generation."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import core.behavioral_evidence_execution_plan as owner
import core.behavioral_validation_specification as spec_owner
from core.structural_compile_validation import CompilerResult, normalize_structural_compile_result
from scripts.replay_patch_candidate_behavior_exec_plan1 import (
    build, direct_only_planning_fixture, no_execution_planning_effects, planning_fixture, validate,
)
from scripts.replay_patch_candidate_materialize1 import SCENARIOS
from scripts.replay_oop_intent_detect2 import BANK


EVIDENCE_MODES = {"static_already_satisfied", "planned_runtime_evidence",
    "blocked_missing_capability", "blocked_semantic_gap"}
MECHANISMS = {"direct_return", "read_only_reflection", "compile_static_evidence",
    "deterministic_console_input", "unsupported_observation", "direct_state_access", "existing_exact_state_query"}
AUTHORITY_FALSE = ("execution_authorized", "java_execution_authorized",
    "reflection_authorized", "console_authorized", "diagnostic_harness_generation_authorized",
    "test_write_authority", "write_authority", "apply_authority")


@pytest.fixture(scope="module")
def cases():
    return {name: planning_fixture(name) for name in SCENARIOS}


@pytest.fixture(scope="module")
def compatibility(cases):
    return cases["preserve_base_compatibility"]


@pytest.fixture(scope="module")
def compatibility_plan(compatibility):
    with no_execution_planning_effects():
        return build(compatibility)


def obligations(plan):
    return {o["obligation_id"]: o for o in plan.as_dict()["obligations"]}


def scenarios(plan):
    return {s["purpose"]: s for s in plan.as_dict()["scenarios"]}


def states(scenario, moment):
    return {o["subject"]: o for o in scenario["observations"] if o["moment"] == moment}


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_frozen_obligation_has_exact_unchanged_oracle_and_lineage(cases, name):
    fixture = cases[name]
    scope, fresh, candidate, materialized, receipt, specification = fixture
    before = (scope.to_json(), fresh["plan"].to_json(), candidate.to_json(),
        materialized.to_json(), receipt.to_json(), specification.to_json(), fresh["current_source"])
    with no_execution_planning_effects():
        plan = build(fixture)
        assert validate(plan.as_dict(), fixture) == plan
    rows = obligations(plan)
    assert set(rows) == {o.obligation_id for o in specification.obligations}
    for original in specification.obligations:
        row = rows[original.obligation_id]
        assert row["oracle"] == json.loads(json.dumps(asdict(original)))
        assert row["evidence_mode"] in EVIDENCE_MODES
        assert row["evidence_mode"] != "blocked_semantic_gap"
    assert plan.phase_id == "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1"
    assert plan.status == "execution_capability_incomplete"
    assert plan.candidate_fingerprint == candidate.fingerprint
    assert plan.materialization_fingerprint == materialized.fingerprint
    assert plan.compile_receipt_fingerprint == receipt.fingerprint
    assert plan.behavioral_spec_fingerprint == specification.fingerprint
    assert plan.implementation_plan_fingerprint == fresh["plan"].fingerprint
    assert plan.admission_fingerprint == scope.fingerprint
    assert not plan.human_semantic_blockers
    assert before == (scope.to_json(), fresh["plan"].to_json(), candidate.to_json(),
        materialized.to_json(), receipt.to_json(), specification.to_json(), fresh["current_source"])


def test_static_facts_schedule_no_runtime_or_reflection(compatibility_plan, compatibility):
    spec = compatibility[-1]
    static_ids = {o.obligation_id for o in spec.obligations if o.evidence_mode == "static_satisfied"}
    assert static_ids == {"BANK.credential_lifecycle", "BANK.base_savings_transition"}
    assert set(compatibility_plan.static_satisfied_obligations) == static_ids
    for identifier in static_ids:
        row = obligations(compatibility_plan)[identifier]
        assert row["evidence_mode"] == "static_already_satisfied"
        assert not row["scenario_ids"] and not row["blockers"]
    assert all(not static_ids & set(s["obligation_ids"]) for s in scenarios(compatibility_plan).values())


def test_wrong_credential_transfer_shares_auth_return_and_state_scenario(compatibility_plan):
    row = obligations(compatibility_plan)["BANK.authentication_gate"]
    shared = scenarios(compatibility_plan)["wrong_credential_transfer"]
    assert row["evidence_mode"] == "planned_runtime_evidence"
    assert "read_only_reflection" not in row["required_capabilities"]
    assert not row["blockers"]
    assert shared["scenario_id"] in row["scenario_ids"]
    assert {"BANK.authentication_gate", "BANK.failed_auth_no_state_change"} <= set(shared["obligation_ids"])
    assert shared["invocation"]["target"]["name"] == "transferToSavings"
    observed = [o for o in shared["observations"] if o["mechanism"] == "direct_return"]
    assert observed and all(o["target"]["declared_type"] == "boolean" for o in observed)
    assert any(a["declared_type"] == "String" for a in shared["invocation"]["arguments"])


def test_failed_authentication_covers_both_operations_and_both_balances(compatibility_plan):
    plans = scenarios(compatibility_plan)
    row = obligations(compatibility_plan)["BANK.failed_auth_no_state_change"]
    assert row["evidence_mode"] == "blocked_missing_capability"
    assert set(row["scenario_ids"]) == {plans["wrong_credential_transfer"]["scenario_id"],
        plans["wrong_credential_interest"]["scenario_id"]}
    for purpose in ("wrong_credential_transfer", "wrong_credential_interest"):
        scenario = plans[purpose]
        for moment in ("before", "after"):
            assert {"BankAccount::balance", "SavingAccount::savingBalance"} <= set(states(scenario, moment))
    wrong_interest = plans["wrong_credential_interest"]
    assert wrong_interest["setup_invocations"]
    setup = wrong_interest["setup_invocations"][0]
    assert setup["expected_setup_return"] is True
    assert next(a["value"] for a in setup["arguments"] if a["declared_type"] == "double") > 0
    assert "direct_return_observation" in wrong_interest["required_capabilities"]
    assert "read_only_reflection" in row["required_capabilities"]
    assert "deterministic_console_input" in row["required_capabilities"]


def test_success_transfer_has_constructor_fixture_and_precondition_evidence(compatibility_plan):
    scenario = scenarios(compatibility_plan)["successful_transfer"]
    assert scenario["constructor"]["kind"] == "constructor"
    assert scenario["constructor"]["owner"] == "SavingAccount"
    constructor_values = [a["value"] for a in scenario["constructor_arguments"]
        if a["declared_type"] in {"double", "float", "int", "long"}]
    action_values = [a["value"] for a in scenario["invocation"]["arguments"]
        if a["declared_type"] in {"double", "float", "int", "long"}]
    assert constructor_values and action_values
    assert constructor_values[0] > action_values[0] > 0
    assert all(a["provenance"] == "diagnostic_fixture" for a in scenario["constructor_arguments"])
    for moment in ("before", "after"):
        assert {"BankAccount::balance", "SavingAccount::savingBalance"} <= set(states(scenario, moment))
    oracle = obligations(compatibility_plan)["BANK.successful_transfer_conservation"]["oracle"]
    assert {"ordinary_balance_decreases_by_A", "savings_balance_increases_by_A",
        "ordinary_plus_savings_total_conserved"} <= set(oracle["expected_observations"])


def test_failed_debit_trigger_is_implementation_owned_without_new_overdraft_policy(compatibility_plan):
    scenario = scenarios(compatibility_plan)["unsuccessful_debit"]
    opening = next(a["value"] for a in scenario["constructor_arguments"] if a["declared_type"] == "double")
    amount = next(a for a in scenario["invocation"]["arguments"] if a["declared_type"] == "double")
    assert amount["value"] > opening
    assert amount["provenance"] == "implementation_fixture"
    assert amount["evidence_ref"]
    assert "SavingAccount::savingBalance" in states(scenario, "before")
    assert "SavingAccount::savingBalance" in states(scenario, "after")
    oracle = obligations(compatibility_plan)["BANK.unsuccessful_debit_no_credit"]["oracle"]
    assert "savings_balance_not_increased" in oracle["expected_observations"]
    assert "savings_credit_after_unsuccessful_debit" in oracle["forbidden_observations"]
    assert "overdraft" not in compatibility_plan.to_json().lower()


def test_interest_uses_transfer_setup_exact_formula_and_console_input(compatibility_plan, compatibility):
    scenario = scenarios(compatibility_plan)["savings_interest"]
    assert scenario["setup_invocations"]
    assert any(s["target"]["name"] == "transferToSavings" and s["expected_setup_return"] is True
        for s in scenario["setup_invocations"])
    assert scenario["invocation"]["console_input"]["declared_type"] == "String"
    assert "deterministic_console_input" in scenario["required_capabilities"]
    assert "read_only_reflection" in scenario["required_capabilities"]
    for moment in ("before", "after"):
        assert {"BankAccount::balance", "SavingAccount::savingBalance"} <= set(states(scenario, moment))
    expected = next(c for c in compatibility[-1].implementation_calculations
        if c.definition_id == scenario["invocation"]["target"]["definition_id"])
    arguments = scenario["invocation"]["arguments"]
    assert tuple(a["name"] for a in arguments[:2]) == expected.parameter_names
    assert all(a["provenance"] == "diagnostic_fixture" for a in arguments)
    policy = scenario["comparison_policy"]
    assert policy["policy"] == "absolute_plus_relative_tolerance"
    assert 0 < policy["absolute_tolerance"] <= 1e-9
    assert 0 < policy["relative_tolerance"] <= 1e-12
    assert policy["finite_values_required"] is True
    assert policy["provenance"] == "diagnostic_implementation_policy"


def test_exact_reflection_targets_read_only_without_product_api_widening(compatibility_plan, compatibility):
    hashes = {f.path: f.after_sha256 for f in compatibility[3].virtual_files}
    observations = [o for s in scenarios(compatibility_plan).values() for o in s["observations"]
        if o["mechanism"] == "read_only_reflection"]
    assert {o["subject"] for o in observations} == {"BankAccount::balance", "SavingAccount::savingBalance"}
    for observation in observations:
        target = observation["target"]
        assert target["kind"] == "field" and target["declared_type"] == "double"
        assert target["visibility"] == "private"
        assert target["source_sha256"] == hashes[target["path"]]
        assert target["definition_id"] and len(target["definition_sha256"]) == 64
        assert target["qualified_owner"] in {"BankAccount", "SavingAccount"}
        assert observation["reflection_operation"]
        assert "set" not in observation["reflection_operation"].lower()
    payload = compatibility_plan.to_json()
    assert "getDeclaredFields" not in payload
    assert "getter" not in payload.lower()


def test_capabilities_are_truthful_and_do_not_grant_execution(compatibility_plan):
    capabilities = {c["capability"]: c for c in compatibility_plan.as_dict()["required_diagnostic_capabilities"]}
    assert capabilities["read_only_reflection"]["status"] == "plannable_but_not_authorized"
    assert capabilities["deterministic_console_input"]["status"] in {"unavailable", "unsupported"}
    assert capabilities["direct_return_observation"]["status"] == "available_by_existing_surface"
    assert capabilities["direct_public_invocation"]["status"] == "available_by_existing_surface"
    console = capabilities["deterministic_console_input"]
    assert "stdin" in console["limitation"].lower()
    assert console["evidence_refs"]
    assert not {"network", "clock", "randomness", "filesystem", "database"} & capabilities.keys()
    assert compatibility_plan.unresolved_capability_blockers
    assert compatibility_plan.authority == "behavioral_execution_plan_only"
    assert all(getattr(compatibility_plan, key) is False for key in AUTHORITY_FALSE)


def test_minimal_scenarios_use_independent_fresh_instances(compatibility_plan):
    rows = scenarios(compatibility_plan)
    assert set(rows) == {"wrong_credential_transfer", "wrong_credential_interest", "successful_transfer",
        "unsuccessful_debit", "savings_interest"}
    assert len({s["scenario_id"] for s in rows.values()}) == 5
    assert all(s["isolation"] == "fresh_candidate_instance" for s in rows.values())
    for scenario in rows.values():
        assert scenario["constructor"] and scenario["constructor_arguments"]
        assert scenario["obligation_ids"]
        assert all(o["mechanism"] in MECHANISMS for o in scenario["observations"])


def test_specialization_follows_admitted_method_and_nested_exact_owner(cases):
    with no_execution_planning_effects():
        specialization = build(cases["subclass_specialization"])
        nested = build(cases["nested"])
    assert scenarios(specialization)["savings_interest"]["invocation"]["target"]["name"] == "saving"
    nested_target = scenarios(nested)["savings_interest"]["invocation"]["target"]
    assert nested_target["qualified_owner"] == "BankAccount::SavingAccount"
    assert nested_target["path"] == "bank.java"
    assert scenarios(nested)["savings_interest"]["constructor"]["qualified_owner"] == "BankAccount::SavingAccount"
    assert next(s.invocation.target.binary_owner for s in nested.scenarios if s.purpose == "savings_interest") == "BankAccount$SavingAccount"
    base = obligations(build(cases["savings_only_on_subclass"]))["BANK.base_savings_transition"]
    assert base["evidence_mode"] == "static_already_satisfied" and not base["scenario_ids"]


@pytest.mark.parametrize("part", ("receipt", "materialized", "candidate", "admission", "plan", "source", "transition", "spec"))
def test_every_freshness_input_is_reconstructed_and_stale_rejected(cases, compatibility_plan, part):
    fixture = cases["preserve_base_compatibility"]
    changes = {}
    if part == "receipt":
        changes["compile_receipt"] = cases["nested"][4]
    elif part == "materialized":
        changes["materialized"] = cases["nested"][3]
    elif part == "candidate":
        payload = fixture[2].as_dict()
        payload["candidate_fingerprint"] = "b" * 64
        changes["candidate"] = payload
    elif part == "admission":
        changes["admitted_scope"] = cases["subclass_specialization"][0]
    elif part == "plan":
        changes["plan"] = cases["subclass_specialization"][1]["plan"]
    elif part == "source":
        changes["current_source"] = fixture[1]["current_source"] + b"\n// stale"
    elif part == "transition":
        changes["scope_transition_effective_design"] = cases["savings_only_on_subclass"][1]["scope_transition_effective_design"]
    else:
        changes["specification"] = cases["nested"][-1]
    with no_execution_planning_effects():
        for operation in (lambda: build(fixture, **changes),
                lambda: validate(compatibility_plan, fixture, **changes)):
            with pytest.raises(owner.BehavioralExecutionPlanError) as rejected:
                operation()
            assert rejected.value.code == "execution_plan_stale"


def test_compile_gate_rejects_failed_provider_evidence(compatibility):
    scope, fresh, candidate, materialized, receipt, _ = compatibility
    failed = normalize_structural_compile_result(materialized,
        compiler_result=CompilerResult(compiler=receipt.compiler_result.compiler, exit_code=1),
        candidate=candidate, admitted_scope=scope, **fresh)
    with no_execution_planning_effects():
        with pytest.raises(owner.BehavioralExecutionPlanError) as rejected:
            build(compatibility, compile_receipt=failed)
    assert rejected.value.code in {"execution_plan_stale", "execution_plan_unavailable"}


def test_unproved_constructor_initialization_blocks_setup_without_human_question():
    fixture = planning_fixture(source=BANK.replace("this.balance = opening;", "this.balance = opening + 2;"))
    with no_execution_planning_effects():
        plan = build(fixture)
        assert validate(plan, fixture) == plan
    assert plan.status == "execution_capability_incomplete"
    assert not plan.human_semantic_blockers
    assert any(c.capability == "execution_setup_unavailable" and c.status == "unavailable"
        for c in plan.required_diagnostic_capabilities)
    assert all(row.evidence_mode == "blocked_missing_capability"
        for row in plan.obligations if row.oracle.evidence_mode != "static_satisfied")


def test_packaged_target_uses_exact_candidate_binary_owner(cases):
    with no_execution_planning_effects():
        plan = build(cases["packaged"])
    target = next(s.invocation.target for s in plan.scenarios if s.purpose == "savings_interest")
    assert target.package_name == "edu"
    assert target.binary_owner == "edu.SavingAccount"
    assert target.path == "edu/SavingAccount.java"


@pytest.mark.parametrize("field", AUTHORITY_FALSE)
def test_authority_escalation_rejected_even_nested(compatibility, compatibility_plan, field):
    payload = deepcopy(compatibility_plan.as_dict())
    payload[field] = True
    with no_execution_planning_effects():
        with pytest.raises(owner.BehavioralExecutionPlanError) as rejected:
            validate(payload, compatibility)
    assert rejected.value.code == "execution_plan_authority_escalation"
    nested = deepcopy(compatibility_plan.as_dict())
    nested["scenarios"][0][field] = True
    with no_execution_planning_effects():
        with pytest.raises(owner.BehavioralExecutionPlanError) as rejected:
            validate(nested, compatibility)
    assert rejected.value.code == "execution_plan_authority_escalation"


def test_authority_label_cannot_be_replaced_by_execution_grant(compatibility, compatibility_plan):
    payload = compatibility_plan.as_dict()
    payload["authority"] = "behavioral_execution_authorized"
    with no_execution_planning_effects():
        with pytest.raises(owner.BehavioralExecutionPlanError) as rejected:
            validate(payload, compatibility)
    assert rejected.value.code == "execution_plan_authority_escalation"


@pytest.mark.parametrize("field,value", (("java_source", "class Harness {}"),
    ("junit_source", "@Test void test() {}"), ("test_source", "assert balance"),
    ("shell_command", "java Harness"), ("java_command", ["java", "SavingAccount"]),
    ("javac_command", ["javac", "SavingAccount.java"]), ("command", "java Harness"),
    ("test_file", "SavingAccountBehaviorTest.java"), ("getDeclaredFields", True)))
def test_executable_source_and_commands_rejected_recursively(compatibility, compatibility_plan, field, value):
    for nested in (False, True):
        payload = deepcopy(compatibility_plan.as_dict())
        (payload["scenarios"][0] if nested else payload)[field] = value
        with no_execution_planning_effects():
            with pytest.raises(owner.BehavioralExecutionPlanError) as rejected:
                validate(payload, compatibility)
        assert rejected.value.code == "execution_plan_invalid"


@pytest.mark.parametrize("part", ("oracle", "method", "field", "hash", "reflection_write", "tolerance", "coverage", "fingerprint"))
def test_typed_targets_oracle_coverage_and_reflection_contract_cannot_drift(compatibility, compatibility_plan, part):
    payload = deepcopy(compatibility_plan.as_dict())
    if part == "oracle":
        payload["obligations"][0]["oracle"]["expected_observations"].append("three_password_attempts")
    elif part == "method":
        payload["scenarios"][0]["invocation"]["target"]["name"] = "unboundMethod"
    elif part in {"field", "hash", "reflection_write"}:
        observation = next(o for s in payload["scenarios"] for o in s["observations"]
            if o["mechanism"] == "read_only_reflection")
        if part == "field":
            observation["target"]["name"] = "balanceLikeField"
        elif part == "hash":
            observation["target"]["source_sha256"] = "b" * 64
        else:
            observation["reflection_operation"] = "write_field"
    elif part == "tolerance":
        payload["scenarios"][0]["comparison_policy"]["absolute_tolerance"] = 100.0
    elif part == "coverage":
        payload["obligations"] = payload["obligations"][1:]
    else:
        payload["execution_plan_fingerprint"] = "b" * 64
    with no_execution_planning_effects():
        with pytest.raises(owner.BehavioralExecutionPlanError) as rejected:
            validate(payload, compatibility)
    assert rejected.value.code in {"execution_plan_invalid", "execution_plan_stale",
        "execution_plan_oracle_drift", "execution_plan_authority_escalation"}


@pytest.mark.parametrize("policy", ("three_password_attempts", "lockout", "transaction_fee", "new_balance_policy"))
def test_diagnostic_plan_cannot_add_domain_policies(compatibility, compatibility_plan, policy):
    payload = deepcopy(compatibility_plan.as_dict())
    payload["obligations"][0]["oracle"]["expected_observations"].append(policy)
    with no_execution_planning_effects():
        with pytest.raises(owner.BehavioralExecutionPlanError) as rejected:
            validate(payload, compatibility)
    assert rejected.value.code in {"execution_plan_stale", "execution_plan_oracle_drift", "execution_plan_invalid"}


def test_full_spec_validation_is_required_before_inventory_planning(compatibility):
    with no_execution_planning_effects(), patch.object(spec_owner,
            "validate_behavioral_validation_specification", wraps=spec_owner.validate_behavioral_validation_specification) as gate:
        build(compatibility)
    assert gate.call_count >= 1


def test_immutable_idempotent_timing_is_external(compatibility):
    timings_a, timings_b = {}, {}
    with no_execution_planning_effects():
        a = build(compatibility, timings=timings_a)
        b = build(compatibility, timings=timings_b)
        assert validate(a.as_dict(), compatibility) == a
    assert a == b and a.fingerprint == b.fingerprint
    assert a.obligations == b.obligations and a.scenarios == b.scenarios
    assert json.loads(a.to_json()) == a.as_dict()
    assert set(timings_a) == set(timings_b) == set(owner.TIMING_FIELDS)
    assert all(type(value) is float and value >= 0 for value in timings_a.values())
    assert "timings" not in a.as_dict()
    with pytest.raises(FrozenInstanceError):
        a.status = "execution_ready"
    with pytest.raises(FrozenInstanceError):
        a.scenarios[0].purpose = "arbitrary_execution"
    with pytest.raises(owner.BehavioralExecutionPlanError):
        replace(a, scenarios=list(a.scenarios))


def test_zero_effect_authority_serialization_and_proposed_test_handling(compatibility_plan):
    payload = compatibility_plan.as_dict()
    assert all(payload[k] is False for k in AUTHORITY_FALSE)
    for key in ("model_calls", "author_calls", "repository_traversals", "source_mutation",
            "test_generation_count", "java_execution_count", "javac_calls",
            "reflection_execution_count", "console_open_count", "diagnostic_harness_generation_count"):
        assert payload[key] == 0
    assert payload["diagnostic_harness_required"] is True
    assert payload["harness_kind"] == "future_ephemeral_diagnostic_harness"
    assert payload["test_file_handling"] == "proposed_product_test_paths_are_not_execution_targets"
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
    assert payload["first_remaining_blocker"] == "STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_NOT_IMPLEMENTED"


def test_bookkeeping_reversal_preserves_frozen_prerequisite_entry_receipts():
    from tests._patch_candidate_behavior_exec_plan1_maintenance import before_patch_candidate_behavior_exec_plan1
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tests/fixtures/patch_candidate_behavior_exec_plan1_reversal.json").read_text(encoding="utf-8"))
    for record in receipt["reversals"]:
        restored = before_patch_candidate_behavior_exec_plan1(record["path"], (root / record["path"]).read_bytes())
        assert sha256(restored).hexdigest() == record["entry_sha256"]
        with pytest.raises(AssertionError):
            before_patch_candidate_behavior_exec_plan1(record["path"], (root / record["path"]).read_bytes() + b"\n")


def test_direct_only_ready_fixture_passes_full_frozen_validation_without_authority():
    fixture = direct_only_planning_fixture()
    before = tuple(v.to_json() for v in (fixture[0], fixture[2], fixture[3], fixture[4], fixture[5]))
    with no_execution_planning_effects():
        plan = build(fixture)
        assert validate(plan.as_dict(), fixture) == plan
    assert plan.status == "execution_ready"
    assert not plan.unresolved_capability_blockers and not plan.human_semantic_blockers
    capabilities = {c.capability for c in plan.required_diagnostic_capabilities}
    assert "read_only_reflection" not in capabilities and "deterministic_console_input" not in capabilities
    assert all(c.status == "available_by_existing_surface" for c in plan.required_diagnostic_capabilities)
    assert all(row["evidence_mode"] in {"static_already_satisfied", "planned_runtime_evidence"}
        for row in obligations(plan).values())
    interest = scenarios(plan)["savings_interest"]
    assert interest["invocation"]["console_input"] is None
    assert tuple(a["name"] for a in interest["invocation"]["arguments"]) == ("rate", "period", "providedPassword")
    assert all(getattr(plan, key) is False for key in AUTHORITY_FALSE)
    assert before == tuple(v.to_json() for v in (fixture[0], fixture[2], fixture[3], fixture[4], fixture[5]))


def test_diagnostic_action_follows_exact_admitted_role_even_when_method_is_renamed():
    fixture = direct_only_planning_fixture(transfer_name="moveToSavings")
    with no_execution_planning_effects():
        plan = build(fixture)
        assert validate(plan, fixture) == plan
    assert plan.status == "execution_ready"
    failed = scenarios(plan)["unsuccessful_debit"]
    assert failed["invocation"]["target"]["name"] == "moveToSavings"
    amount = next(a for a in failed["invocation"]["arguments"] if a["declared_type"] == "double")
    opening = next(a["value"] for a in failed["constructor_arguments"] if a["declared_type"] == "double")
    assert amount["value"] > opening and amount["provenance"] == "implementation_fixture"


def test_every_exact_admitted_transfer_target_has_its_own_auth_and_state_routes():
    fixture = direct_only_planning_fixture(extra_transfer=True)
    specification = fixture[-1]
    auth = next(o for o in specification.obligations if o.semantic_dimension == "authentication_gate")
    targets = {t.definition_id for t in auth.target_definitions if t.kind == "method"}
    assert len(targets) == 2
    with no_execution_planning_effects():
        plan = build(fixture)
        assert validate(plan, fixture) == plan
    assert plan.status == "execution_ready"
    for purpose in ("wrong_credential_transfer", "successful_transfer", "unsuccessful_debit"):
        selected = [s for s in plan.scenarios if s.purpose == purpose]
        assert len(selected) == 2
        assert {s.invocation.target.definition_id for s in selected} == targets
    rows = obligations(plan)
    assert len(rows["BANK.authentication_gate"]["scenario_ids"]) == 2
    assert len(rows["BANK.failed_auth_no_state_change"]["scenario_ids"]) == 3
    assert len(rows["BANK.successful_transfer_conservation"]["scenario_ids"]) == 2
    assert len(rows["BANK.unsuccessful_debit_no_credit"]["scenario_ids"]) == 2
    assert len({s.scenario_id for s in plan.scenarios}) == len(plan.scenarios) == 8
