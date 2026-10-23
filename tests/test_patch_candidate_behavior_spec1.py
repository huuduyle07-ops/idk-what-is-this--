"""Declarative oracle projection only; these Python checks never execute Java."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import core.behavioral_validation_specification as owner
from core.structural_candidate_materialization import materialize_structural_candidate
from core.structural_compile_validation import (
    CompilerResult, JavacIdentity, normalize_structural_compile_result,
)
from scripts.replay_patch_candidate_materialize1 import (
    SCENARIOS, synthetic_candidate_case,
)
from scripts.replay_patch_candidate_behavior_spec1 import no_specification_effects
from scripts.replay_oop_intent_detect2 import BANK


FAMILIES = frozenset({
    "authentication_gate", "failed_auth_no_state_change",
    "successful_transfer_conservation", "unsuccessful_debit_no_credit",
    "savings_interest_target", "credential_lifecycle", "base_savings_transition",
})
EVIDENCE_MODES = frozenset({"static_satisfied", "runtime_required", "unresolved_observability"})


def synthetic_compile_result(**changes):
    """A replayable measured-result fixture, with no compiler invocation."""
    identity = JavacIdentity(str(Path("C:/trusted/javac.exe")), "a" * 64, "javac 23.0.2")
    return CompilerResult(**{"compiler": identity, "exit_code": 0, **changes})


def specification_fixture(name="preserve_base_compatibility", *, source=None, result=None):
    scope, fresh, candidate = synthetic_candidate_case(name, source=source)
    materialized = materialize_structural_candidate(candidate, admitted_scope=scope, **fresh)
    receipt = normalize_structural_compile_result(materialized,
        compiler_result=result or synthetic_compile_result(), candidate=candidate,
        admitted_scope=scope, **fresh)
    return scope, fresh, candidate, materialized, receipt


def project(fixture, **changes):
    scope, fresh, candidate, materialized, receipt = fixture
    return owner.project_behavioral_validation_specification(**{
        "compile_receipt": receipt, "materialized": materialized, "candidate": candidate,
        "admitted_scope": scope, **fresh, **changes,
    })


def validate(spec, fixture, **changes):
    scope, fresh, candidate, materialized, receipt = fixture
    return owner.validate_behavioral_validation_specification(spec, **{
        "compile_receipt": receipt, "materialized": materialized, "candidate": candidate,
        "admitted_scope": scope, **fresh, **changes,
    })


def family(spec, name):
    return tuple(o for o in spec.obligations if o.semantic_dimension == name)


def observation_subjects(obligations):
    return {c.subject for o in obligations for c in o.required_observation_capability}


def provenance(obligations):
    return tuple(p for o in obligations for p in o.provenance)


@pytest.fixture(scope="module")
def cases():
    return {name: specification_fixture(name) for name in SCENARIOS}


@pytest.fixture(scope="module")
def compatibility(cases):
    return cases["preserve_base_compatibility"]


@pytest.fixture(scope="module")
def compatibility_spec(compatibility):
    return project(compatibility)


@pytest.mark.parametrize("name", SCENARIOS)
def test_complete_frozen_candidate_lineage_projects_closed_behavior_families(cases, name):
    fixture = cases[name]
    scope, fresh, candidate, materialized, receipt = fixture
    before = (scope.to_json(), fresh["plan"].to_json(), candidate.to_json(),
        materialized.to_json(), receipt.to_json(), fresh["current_source"])
    with no_specification_effects():
        spec = project(fixture)
        assert validate(spec.as_dict(), fixture) == spec
    assert spec.phase_id == "PATCH.CANDIDATE.BEHAVIOR.SPEC.1"
    assert {o.semantic_dimension for o in spec.obligations} == FAMILIES
    assert spec.task_fingerprint == receipt.task_fingerprint
    assert spec.effective_design_fingerprint == receipt.effective_design_fingerprint
    assert spec.implementation_plan_fingerprint == fresh["plan"].fingerprint
    assert spec.candidate_fingerprint == candidate.fingerprint
    assert spec.materialization_fingerprint == materialized.fingerprint
    assert spec.compile_receipt_fingerprint == receipt.fingerprint
    assert before == (scope.to_json(), fresh["plan"].to_json(), candidate.to_json(),
        materialized.to_json(), receipt.to_json(), fresh["current_source"])
    assert not spec.unresolved_oracle_gaps
    assert spec.proposed_test_files == ("SavingAccountBehaviorTest.java",)


def test_obligations_bind_exact_virtual_definitions_and_materialization_hashes(
        compatibility, compatibility_spec):
    materialized = compatibility[3]
    hashes = {v.path: v.after_sha256 for v in materialized.virtual_files}
    identifiers = [o.obligation_id for o in compatibility_spec.obligations]
    assert len(identifiers) == len(set(identifiers))
    for obligation in compatibility_spec.obligations:
        assert obligation.materiality == "required"
        assert obligation.evidence_mode in EVIDENCE_MODES
        assert obligation.evidence_refs and obligation.provenance
        assert obligation.target_definitions and obligation.materialization_hashes
        for path, digest in obligation.materialization_hashes:
            assert hashes[path] == digest
        for target in obligation.target_definitions:
            assert target.path in hashes
            assert target.owner in {"BankAccount", "SavingAccount"}
            assert target.definition_id and target.name and target.kind
        for ref in obligation.evidence_refs:
            assert type(ref) is str and ref
        for record in obligation.provenance:
            assert record.kind in {"explicit_human", "implementation_contract", "measured_structural"}
            assert record.evidence_ref in obligation.evidence_refs


def test_typed_coverage_and_evidence_requirements_cover_each_obligation(compatibility_spec):
    spec = compatibility_spec
    obligations = {o.obligation_id: o for o in spec.obligations}
    human_dimensions = {p.dimension for o in spec.obligations for p in o.provenance
        if p.kind == "explicit_human"}
    assert human_dimensions <= {c.semantic_dimension for c in spec.coverage}
    covered = set()
    for row in spec.coverage:
        assert row.evidence_mode in EVIDENCE_MODES and row.obligation_ids
        for identifier in row.obligation_ids:
            assert identifier in obligations
            covered.add(identifier)
    assert covered == set(obligations)
    assert {r.obligation_id for r in spec.evidence_requirements} == set(obligations)
    for requirement in spec.evidence_requirements:
        obligation = obligations[requirement.obligation_id]
        assert requirement.evidence_mode == obligation.evidence_mode
        assert set(requirement.observation_subjects) == observation_subjects((obligation,))


def test_machine_checkable_authentication_and_state_nonchange_relations(compatibility_spec):
    gate = family(compatibility_spec, "authentication_gate")
    assert gate and all("incorrect_credential" in o.preconditions for o in gate)
    assert any("transfer_returns_false" in o.expected_observations for o in gate)
    failed = family(compatibility_spec, "failed_auth_no_state_change")
    assert failed and all("incorrect_credential" in o.preconditions for o in failed)
    for obligation in failed:
        assert {"ordinary_balance_unchanged", "savings_balance_unchanged"} <= set(obligation.expected_observations)
        assert "protected_transition_after_failed_verification" in obligation.forbidden_observations
    assert {t.name for o in failed for t in o.target_definitions} >= {
        "transferToSavings", "accrueSavingsInterest", "balance", "savingBalance"}


def test_machine_checkable_transfer_conservation_and_failed_debit_relations(compatibility_spec):
    transfer = family(compatibility_spec, "successful_transfer_conservation")
    assert transfer
    for obligation in transfer:
        assert {"correct_credential", "successful_inherited_debit", "transfer_amount_A"} <= set(obligation.preconditions)
        assert {"ordinary_balance_decreases_by_A", "savings_balance_increases_by_A",
            "ordinary_plus_savings_total_conserved"} <= set(obligation.expected_observations)
    failed = family(compatibility_spec, "unsuccessful_debit_no_credit")
    assert failed
    for obligation in failed:
        assert {"correct_credential", "unsuccessful_inherited_debit"} <= set(obligation.preconditions)
        assert "savings_balance_not_increased" in obligation.expected_observations
        assert "savings_credit_after_unsuccessful_debit" in obligation.forbidden_observations
    assert any(p.kind == "explicit_human" and p.value == "transfer_from_inherited_balance"
        for p in provenance(transfer))
    assert any(p.kind == "implementation_contract" for p in provenance(failed))


def test_interest_oracle_distinguishes_principal_without_financial_policy(compatibility_spec):
    interest = family(compatibility_spec, "savings_interest_target")
    assert interest
    for obligation in interest:
        assert {"correct_credential", "distinct_ordinary_and_savings_principals",
            "admitted_interest_parameters"} <= set(obligation.preconditions)
        assert {"candidate_selected_simple_interest_on_savings_principal",
            "ordinary_balance_unchanged"} <= set(obligation.expected_observations)
        assert "ordinary_balance_used_as_interest_principal" in obligation.forbidden_observations


def test_obligation_vocabulary_remains_closed(compatibility_spec):
    for obligation in compatibility_spec.obligations:
        assert set(obligation.preconditions) <= owner.PRECONDITIONS
        assert obligation.action in owner.ACTIONS
        assert set((*obligation.expected_observations, *obligation.forbidden_observations)) <= owner.OBSERVATIONS


def test_private_state_blocks_exact_conservation_despite_boolean_return(compatibility_spec):
    conservation = family(compatibility_spec, "successful_transfer_conservation")
    assert conservation
    assert all(o.status == "observation_evidence_missing" and
        o.evidence_mode == "unresolved_observability" for o in conservation)
    capabilities = [c for o in conservation for c in o.required_observation_capability]
    assert any(c.subject == "BankAccount::balance" and not c.available for c in capabilities)
    assert any(c.subject == "SavingAccount::savingBalance" and not c.available for c in capabilities)
    capabilities += [c for o in family(compatibility_spec, "authentication_gate")
        for c in o.required_observation_capability]
    assert any(c.capability == "method_return" and c.available for c in capabilities)
    gap_subjects = {g.subject for g in compatibility_spec.observation_gaps}
    assert {"BankAccount::balance", "SavingAccount::savingBalance"} <= gap_subjects
    for gap in compatibility_spec.observation_gaps:
        assert gap.status == "observation_evidence_missing"
        assert gap.obligation_ids and gap.required_capability


def test_console_input_is_a_harness_constraint_without_compile_or_semantic_repair(compatibility_spec):
    interest = family(compatibility_spec, "savings_interest_target")
    interest_ids = {o.obligation_id for o in interest}
    constraints = compatibility_spec.execution_harness_constraints
    assert constraints
    assert any(set(c.obligation_ids) & interest_ids for c in constraints)
    for constraint in constraints:
        assert constraint.status == "execution_harness_constraint"
        assert constraint.capability == "console_input"
        assert constraint.reason == "System.console_requires_console"
        assert constraint.target_definitions
    assert not compatibility_spec.unresolved_oracle_gaps


@pytest.mark.parametrize("transition", SCENARIOS[:3])
def test_console_harness_constraint_does_not_request_execution_for_static_facts(cases, transition):
    with no_specification_effects():
        spec = project(cases[transition])
    static_ids = {o.obligation_id for o in spec.obligations if o.evidence_mode == "static_satisfied"}
    assert spec.execution_harness_constraints
    assert all(not static_ids & set(c.obligation_ids) for c in spec.execution_harness_constraints)


@pytest.mark.parametrize("prior_query,ordinary_available", (
    ("double balanceForEvidence() { return this.balance; }", True),
    ("private double balanceForEvidence() { return balance; }", False),
    ("double doubledBalance() { return balance * 2; }", False),
    ("void displayBalance() { System.out.println(balance); }", False),
))
def test_prior_exact_query_is_used_but_private_or_display_api_cannot_close_state_gap(
        prior_query, ordinary_available):
    source = BANK.replace("  void deposit", "  " + prior_query + "\n  void deposit")
    fixture = specification_fixture(source=source)
    before = fixture[1]["current_source"], fixture[2].to_json(), fixture[3].to_json()
    with no_specification_effects():
        spec = project(fixture)
    conservation = family(spec, "successful_transfer_conservation")
    capabilities = [c for o in conservation for c in o.required_observation_capability]
    ordinary = [c for c in capabilities if c.subject == "BankAccount::balance"]
    assert ordinary and all(c.available is ordinary_available for c in ordinary)
    if ordinary_available:
        assert all(c.capability == "existing_exact_state_query" for c in ordinary)
    assert all(o.status == "observation_evidence_missing" for o in conservation)
    assert any(c.subject == "SavingAccount::savingBalance" and not c.available for c in capabilities)
    assert before == (fixture[1]["current_source"], fixture[2].to_json(), fixture[3].to_json())


def test_in_memory_credential_is_static_evidence_without_runtime_persistence_sweep(compatibility_spec):
    lifecycle = family(compatibility_spec, "credential_lifecycle")
    assert lifecycle and all(o.evidence_mode == o.status == "static_satisfied" for o in lifecycle)
    assert any(p.kind == "explicit_human" and p.value == "in_memory_only" for p in provenance(lifecycle))
    assert any(p.kind == "measured_structural" for p in provenance(lifecycle))
    assert all(c.available for o in lifecycle for c in o.required_observation_capability)


def test_interest_target_has_human_provenance_but_formula_is_implementation_contract(compatibility_spec):
    interest = family(compatibility_spec, "savings_interest_target")
    records = provenance(interest)
    assert any(p.kind == "explicit_human" and p.value == "interest_applies_to_saving_balance" for p in records)
    assert any(p.kind == "implementation_contract" for p in records)
    assert not any(p.kind == "explicit_human" and
        any(token in p.value.lower() for token in ("simple_rate", "simple_interest", "formula"))
        for p in records)


@pytest.mark.parametrize("name", ("preserve_base_compatibility", "subclass_specialization", "nested"))
def test_interest_calculation_binds_admitted_parameter_order_and_implementation_provenance(cases, name):
    fixture = cases[name]
    spec = project(fixture)
    definitions = {a.definition.identity: a.definition for a in fixture[0].definition_allowances}
    interest_targets = {t.definition_id for o in family(spec, "savings_interest_target")
        for t in o.target_definitions if "savings_interest_behavior" in
        getattr(definitions.get(t.definition_id), "roles", ())}
    assert {c.definition_id for c in spec.implementation_calculations} == interest_targets
    for calculation in spec.implementation_calculations:
        definition = definitions[calculation.definition_id]
        assert calculation.parameter_names == tuple(name for _, name in definition.parameters[:2])
        assert calculation.principal == "SavingAccount::savingBalance"
        assert calculation.operation == "add_principal_times_selected_parameters"
        assert calculation.provenance == "implementation_contract"
        assert "plan:" + fixture[1]["plan"].fingerprint in calculation.evidence_refs
        assert "candidate:" + fixture[2].fingerprint in calculation.evidence_refs
        assert "materialization:" + fixture[3].fingerprint in calculation.evidence_refs


def test_interest_projection_uses_typed_contract_without_parsing_planner_rationale():
    import scripts.replay_patch_author_structural1 as author_replay
    original = author_replay.synthetic_planner_proposal
    def changed_rationale(*args, **kwargs):
        proposal = original(*args, **kwargs)
        return replace(proposal, implementation_decisions=tuple(
            replace(d, choice="Verify each operation and apply the selected admitted rate operation only to savingBalance")
            if d.area == "savings_interest" else d for d in proposal.implementation_decisions))
    with patch.object(author_replay, "synthetic_planner_proposal", changed_rationale):
        fixture = specification_fixture()
    with no_specification_effects():
        spec = project(fixture)
        assert validate(spec, fixture) == spec
    assert spec.implementation_calculations and not spec.unresolved_oracle_gaps
    assert any("candidate_selected_simple_interest_on_savings_principal" in o.expected_observations
        for o in family(spec, "savings_interest_target"))


def test_nested_same_named_bank_shadow_cannot_supply_private_base_state_observation():
    source = BANK + "\nclass Outer { static class BankAccount { public double balance; public double readState() { return balance; } } }"
    fixture = specification_fixture(source=source)
    assert b"class Outer" in fixture[1]["current_source"]
    with no_specification_effects():
        spec = project(fixture)
        assert validate(spec.as_dict(), fixture) == spec
    capabilities = [c for o in family(spec, "successful_transfer_conservation")
        for c in o.required_observation_capability if c.subject == "BankAccount::balance"]
    assert capabilities and all(not c.available for c in capabilities)
    assert all(c.capability == "reflection_required" for c in capabilities)
    targets = [t for o in spec.obligations for t in o.target_definitions if t.owner == "BankAccount"]
    assert targets and all(not t.qualified_owner.startswith("Outer::") for t in targets)


def test_nested_savings_shadow_cannot_supply_another_class_state_at_observation_seam(cases):
    fixture = cases["nested"]
    materialized = fixture[3]
    with no_specification_effects():
        spec = project(fixture)
    target = next(t for o in spec.obligations for t in o.target_definitions
        if t.owner == "SavingAccount" and t.name == "savingBalance")
    assert target.qualified_owner == "BankAccount::SavingAccount"
    virtual = materialized.virtual_files[0]
    before = materialized.to_json()
    augmented_source = virtual.after_source + "\nclass Outer { static class SavingAccount { public double savingBalance; public double readState() { return savingBalance; } } }"
    augmented_bytes = augmented_source.encode("utf-8")
    augmented = replace(materialized, virtual_files=(replace(virtual, after_source=augmented_source,
        after_sha256=sha256(augmented_bytes).hexdigest(), after_size=len(augmented_bytes)),))
    # Exercise the observation seam alone: this synthetic buffer has no new
    # compile receipt and is never projected or claimed as a valid candidate.
    with no_specification_effects():
        inventory = owner._observation_inventory(augmented, fixture[1])
        capability = owner._state_capability(target, inventory, augmented)
    assert inventory[(target.path, "Outer::SavingAccount", "savingBalance", "field")][0] == "public"
    assert inventory[(target.path, "BankAccount::SavingAccount", "savingBalance", "field")][0] == "private"
    assert capability.subject == "SavingAccount::savingBalance"
    assert capability.available is False and capability.capability == "reflection_required"
    assert materialized.to_json() == before


def test_all_runtime_required_evidence_is_pending_after_compile_success(compatibility_spec):
    runtime = [o for o in compatibility_spec.obligations if o.evidence_mode == "runtime_required"]
    assert runtime and all(o.status == "runtime_required" for o in runtime)
    assert not compatibility_spec.behavior_validated
    assert not compatibility_spec.correctness_proven
    assert compatibility_spec.behavioral_validation_pending


@pytest.mark.parametrize("transition", SCENARIOS[:3])
def test_base_transition_oracle_preserves_exact_chosen_semantic_commitment(cases, transition):
    spec = project(cases[transition])
    base = family(spec, "base_savings_transition")
    assert base
    assert any(p.value == transition for p in provenance(base))
    assert not any(p.value in set(SCENARIOS[:3]) - {transition} for p in provenance(base))
    oracle = " ".join(code for o in base for code in
        (*o.preconditions, o.action, *o.expected_observations, *o.forbidden_observations))
    assert "delete" not in oracle.lower() and "annotation" not in oracle.lower()
    assert "@Override" not in oracle


def test_nesting_changes_physical_bindings_without_inventing_behavior(cases):
    top = project(cases["preserve_base_compatibility"])
    nested = project(cases["nested"])
    def semantic_rows(spec):
        return [(o.semantic_dimension, o.preconditions, o.action, o.expected_observations,
            o.forbidden_observations, o.evidence_mode, o.status,
            tuple((p.kind, p.dimension, p.value) for p in o.provenance)) for o in spec.obligations]
    assert semantic_rows(top) == semantic_rows(nested)
    assert {t.path for o in nested.obligations for t in o.target_definitions} == {"bank.java"}
    assert top.fingerprint != nested.fingerprint


def test_projection_and_validation_have_no_providers_files_traversal_or_execution(compatibility):
    with no_specification_effects():
        spec = project(compatibility)
        assert validate(spec, compatibility) == spec
    for field in ("model_calls", "author_calls", "repository_traversals", "source_mutation",
            "test_generation_count", "java_execution_count", "command_execution_count"):
        assert getattr(spec, field) == 0
    assert spec.authority == "behavioral_oracle_only"
    for field in ("test_write_authority", "execution_authorized", "write_authority", "apply_authority"):
        assert getattr(spec, field) is False


@pytest.mark.parametrize("result", (
    {"exit_code": 1, "stderr": "SavingAccount.java:6: error: synthetic failure\n    super(opening);\n    ^\n1 error\n"},
    {"exit_code": None, "timed_out": True},
    {"compiler": None, "exit_code": None, "unavailable_reason": "javac_not_found",
        "javac_invocation_count": 0, "version_probe_count": 0},
))
def test_unsuccessful_compile_gate_has_no_behavioral_spec(result):
    fixture = specification_fixture(result=synthetic_compile_result(**result))
    assert not fixture[-1].compile_success
    with no_specification_effects():
        with pytest.raises(owner.BehavioralSpecificationError) as rejected:
            project(fixture)
    assert rejected.value.code == "behavior_spec_unavailable_due_compile_failure"


def test_forged_compile_success_flag_cannot_pass_independent_receipt_reconstruction(compatibility):
    payload = compatibility[-1].as_dict()
    payload["compiler_result"]["exit_code"] = 1
    with no_specification_effects():
        with pytest.raises(owner.BehavioralSpecificationError) as rejected:
            project(compatibility, compile_receipt=payload)
    assert rejected.value.code == "behavior_spec_stale"


@pytest.mark.parametrize("part", ("receipt", "materialized", "candidate", "admission", "plan", "source", "transition"))
def test_complete_lineage_mismatch_rejects_as_stale(cases, compatibility_spec, part):
    fixture = cases["preserve_base_compatibility"]
    scope, fresh, candidate, materialized, receipt = fixture
    changes = {}
    if part == "receipt":
        changes["compile_receipt"] = cases["nested"][-1]
    elif part == "materialized":
        changes["materialized"] = cases["nested"][3]
    elif part == "candidate":
        changes["candidate"] = {**candidate.as_dict(), "candidate_fingerprint": "b" * 64}
    elif part == "admission":
        changes["admitted_scope"] = cases["subclass_specialization"][0]
    elif part == "plan":
        changes["plan"] = cases["subclass_specialization"][1]["plan"]
    elif part == "source":
        changes["current_source"] = fresh["current_source"] + b"\n// newer source"
    else:
        changes["scope_transition_effective_design"] = cases["savings_only_on_subclass"][1]["scope_transition_effective_design"]
    with no_specification_effects():
        for operation in (lambda: project(fixture, **changes),
                lambda: validate(compatibility_spec, fixture, **changes)):
            with pytest.raises(owner.BehavioralSpecificationError) as rejected:
                operation()
            assert rejected.value.code == "behavior_spec_stale"


@pytest.mark.parametrize("field,value", (
    ("authority", "write_authorized"), ("test_write_authority", True),
    ("execution_authorized", True), ("write_authority", True), ("apply_authority", True),
))
def test_authority_escalation_rejects_independently(compatibility, compatibility_spec, field, value):
    payload = compatibility_spec.as_dict()
    payload[field] = value
    with no_specification_effects():
        with pytest.raises(owner.BehavioralSpecificationError) as rejected:
            validate(payload, compatibility)
    assert rejected.value.code == "behavior_spec_authority_escalation"


@pytest.mark.parametrize("field,payload", (
    ("test_code", "assert transfer()"), ("java_source", "class SavingAccountBehaviorTest {}"),
    ("junit_source", "@Test void conservation() {}"), ("assertion_code", "assert balance == before"),
    ("java_command", ["java", "SavingAccount"]), ("javac_command", ["javac", "SavingAccount.java"]),
    ("junit_invocation", ["junit", "SavingAccountBehaviorTest"]), ("shell_command", "java SavingAccount"),
))
def test_spec_rejects_test_source_and_command_payloads(compatibility, compatibility_spec, field, payload):
    value = compatibility_spec.as_dict()
    value[field] = payload
    with no_specification_effects():
        with pytest.raises(owner.BehavioralSpecificationError) as rejected:
            validate(value, compatibility)
    assert rejected.value.code == "behavior_spec_invalid"


@pytest.mark.parametrize("policy", (
    "three_password_attempts", "lockout", "persistence_database", "transaction_fee",
    "overdraft", "password_complexity",
))
def test_new_desired_policies_cannot_enter_oracle(compatibility, compatibility_spec, policy):
    payload = deepcopy(compatibility_spec.as_dict())
    obligation = deepcopy(payload["obligations"][0])
    obligation["obligation_id"] = "invented_" + policy
    obligation["semantic_dimension"] = policy
    payload["obligations"].append(obligation)
    with no_specification_effects():
        with pytest.raises(owner.BehavioralSpecificationError) as rejected:
            validate(payload, compatibility)
    assert rejected.value.code in {"behavior_spec_invalid", "behavior_spec_stale"}
    with pytest.raises(owner.BehavioralSpecificationError) as typed_rejected:
        replace(compatibility_spec.obligations[0], semantic_dimension=policy)
    assert typed_rejected.value.code == "behavior_spec_invalid"


@pytest.mark.parametrize("part", ("observation", "provenance", "target", "hash", "coverage", "gap", "fingerprint", "transition"))
def test_nested_oracle_tampering_is_reconstructed_and_rejected(cases, compatibility_spec, part):
    fixture = cases["preserve_base_compatibility"]
    payload = deepcopy(compatibility_spec.as_dict())
    if part == "observation":
        payload["obligations"][0]["expected_observations"].append("invented_transaction_fee")
    elif part == "provenance":
        payload["obligations"][0]["provenance"][0]["evidence_ref"] = "b" * 64
    elif part == "target":
        payload["obligations"][0]["target_definitions"][0]["name"] = "unapprovedMethod"
    elif part == "hash":
        payload["obligations"][0]["materialization_hashes"][0][1] = "b" * 64
    elif part == "coverage":
        payload["coverage"][0]["obligation_ids"] = []
    elif part == "gap":
        payload["observation_gaps"] = []
    elif part == "fingerprint":
        payload["behavioral_spec_fingerprint"] = "b" * 64
    else:
        subclass = project(cases["savings_only_on_subclass"])
        replacement = next(o for o in subclass.as_dict()["obligations"]
            if o["semantic_dimension"] == "base_savings_transition")
        payload["obligations"] = [replacement if o["semantic_dimension"] == "base_savings_transition" else o
            for o in payload["obligations"]]
    with no_specification_effects():
        with pytest.raises(owner.BehavioralSpecificationError) as rejected:
            validate(payload, fixture)
    assert rejected.value.code in {"behavior_spec_invalid", "behavior_spec_stale"}


def test_immutable_idempotent_projection_and_timing_excluded(compatibility):
    timings_a, timings_b = {}, {}
    with no_specification_effects():
        a = project(compatibility, timings=timings_a)
        b = project(compatibility, timings=timings_b)
        assert validate(a.as_dict(), compatibility) == a
    assert a == b and a.fingerprint == b.fingerprint
    assert a.obligations == b.obligations and a.coverage == b.coverage
    assert json.loads(a.to_json()) == a.as_dict()
    assert set(timings_a) == set(timings_b) == set(owner.TIMING_FIELDS)
    assert all(type(value) is float and value >= 0 for value in timings_a.values())
    assert "timings" not in a.as_dict()
    with pytest.raises(FrozenInstanceError):
        a.authority = "write_authorized"
    with pytest.raises(FrozenInstanceError):
        a.obligations[0].status = "runtime_validated"
    with pytest.raises(owner.BehavioralSpecificationError):
        replace(a, obligations=list(a.obligations))
    with pytest.raises(owner.BehavioralSpecificationError):
        replace(a.obligations[0], expected_observations=list(a.obligations[0].expected_observations))


def test_serialized_oracle_has_no_executable_or_unowned_policy_fields(compatibility_spec):
    forbidden = {"test_code", "java_source", "junit_source", "assertion_code", "shell_command",
        "java_command", "javac_command", "junit_invocation", "source_text", "test_source"}
    def inspect(value):
        if isinstance(value, dict):
            assert not forbidden & value.keys()
            for nested in value.values():
                inspect(nested)
        elif isinstance(value, list):
            for nested in value:
                inspect(nested)
    inspect(compatibility_spec.as_dict())
    serialized = compatibility_spec.to_json().lower()
    for policy in ("lockout", "transaction_fee", "overdraft", "password_complexity", "three_password_attempts"):
        assert policy not in serialized


def test_bookkeeping_reversal_preserves_frozen_prerequisite_entry_receipts():
    from tests._patch_candidate_behavior_spec1_maintenance import before_patch_candidate_behavior_spec1
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tests/fixtures/patch_candidate_behavior_spec1_reversal.json").read_text(encoding="utf-8"))
    for record in receipt["reversals"]:
        restored = before_patch_candidate_behavior_spec1(record["path"], (root / record["path"]).read_bytes())
        assert sha256(restored).hexdigest() == record["entry_sha256"]
