"""PATCH.SCOPE.EXPAND.1: evidence-bound proposals without edit authority.

All Java buffers are synthetic and stay in memory. The BANK.2 answer is the
already frozen CONTINUE.1 complete answer, never a real waiting-session answer.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest

from core.authoring_repair_scope import AuthoringRepairScope
from core.class_semantic_context import project_class_semantic_context
from core.design_intent_continuation import compose_effective_design, continue_design_intent
from core.explicit_design_evidence import BehaviorGate, DesignEvidence, EvidenceSpan
from core.input_understanding import understand_request
from core.oop_intent_detector import detect_missing_future_design_contract
from core.oop_intent_session import bind_human_answer, make_stored_future_design_gap
from core.proposed_design_intent import project_proposed_design_intent
from core.repair_scope import RepairDiagnostic, RepairMember, RepairScope
from core.repository_identity import derive_repository_id
from core.structural_scope_expansion import propose_structural_scope_expansion, scope_fingerprint
import core.structural_scope_expansion as expansion
from core.treesitter_parse import structural_definitions
from scripts.replay_patch_scope_expand1 import fixture_inputs


MEASURED_BANK = """class BankAccount {
  private String accountHolder;
  private double balance;
  BankAccount(String accountHolder, double balance) {
    this.accountHolder = accountHolder;
    this.balance = balance;
  }
  public void deposit(double amount) { balance += amount; }
  public void withdraw(double amount) {
    if (amount <= balance) { balance -= amount; }
  }
  public void saving(double interest, double year) {
    balance += balance * interest * year;
  }
  public void display() { System.out.println(accountHolder + balance); }
}"""

MEMBER_BANK = """class BankAccount {
  private double balance;
  private String password;
  public void deposit(double amount) { balance += amount; }
  public boolean verifyPassword(String password) { return this.password.equals(password); }
}"""


def _call(inputs, **overrides):
    arguments = dict(task_contract=inputs["task_contract"], design_intent=inputs["design_intent"],
                     semantic_detection=inputs["detection"], current_context=inputs["current_context"],
                     current_source=inputs["current_source"], repository_id=inputs["repository_id"])
    arguments.update(overrides)
    return propose_structural_scope_expansion(**arguments)


def _context(source, repository_id, owner="BankAccount", file="bank.java"):
    raw = source.encode("utf-8")
    target = next(item for item in structural_definitions(source, "java")["definitions"]
                  if item["kind"] == "class" and item["name"] == owner)
    return project_class_semantic_context(
        raw=raw, language="java", file=file, target=target,
        expected_source_fingerprint=hashlib.sha256(raw).hexdigest(), repository_id=repository_id), raw


def _base_inputs(repo, task, source=MEASURED_BANK):
    repository_id = derive_repository_id(repo)
    contract = understand_request(task)
    design = project_proposed_design_intent(contract)
    context, raw = _context(source, repository_id)
    detection = detect_missing_future_design_contract(
        task_contract=contract, design_intent=design, current_context=context,
        current_source=raw, repository_id=repository_id)
    return dict(task_contract=contract, design_intent=design, current_context=context,
                current_source=raw, repository_id=repository_id, detection=detection)


def _typed_gate_inputs(repo, members=("BankAccount::deposit",), source=MEMBER_BANK):
    # The frozen projection has no general new-method grammar. These exact
    # identifiers enter through preserved typed BehaviorGate commitments.
    clauses = tuple(f"{member} requires successful password verification." for member in members)
    request = "\n".join(clauses)
    contract = understand_request(request)
    start, gates = 0, []
    for member, clause in zip(members, clauses):
        gates.append(BehaviorGate(member, "successful_password_verification",
                                 EvidenceSpan(clause, start, start + len(clause))))
        start += len(clause) + 1
    evidence = DesignEvidence(behavior_gates=tuple(gates))
    contract = replace(contract, design_evidence=evidence,
                       explicit_evidence=replace(contract.explicit_evidence, design_evidence=evidence))
    design = project_proposed_design_intent(contract)
    assert design.status == "resolved"
    repository_id = derive_repository_id(repo)
    context, raw = _context(source, repository_id)
    first = detect_missing_future_design_contract(
        task_contract=contract, design_intent=design, current_context=context,
        current_source=raw, repository_id=repository_id)
    assert first.status == "clarification_required"
    gap = make_stored_future_design_gap(first, task_text=request, repo_path=str(repo))
    answer = bind_human_answer(gap,
        "Let BankAccount own a simple password in memory. "
        "It does not need to persist across runs. "
        "Verify it when a savings operation is requested.").as_dict()
    continuation = continue_design_intent(
        task_contract=contract, base_design=design, stored_gap=gap, stored_answer=answer,
        current_context=context, current_source=raw, repo_path=str(repo))
    effective = compose_effective_design(design, continuation)
    detection = detect_missing_future_design_contract(
        task_contract=contract, design_intent=effective, current_context=context,
        current_source=raw, repository_id=repository_id, stored_gap=gap,
        stored_answer=answer, repo_path=str(repo))
    assert detection.status == "no_gap"
    return dict(task_contract=contract, design_intent=effective, current_context=context,
                current_source=raw, repository_id=repository_id, detection=detection)


def _repair(inputs, member="deposit", *, authoring=False):
    raw = inputs["current_source"]
    source = raw.decode("utf-8")
    definition = next(item for item in structural_definitions(source, "java")["definitions"]
                      if item["kind"] == "function" and item["name"] == member)
    diagnostic = RepairDiagnostic("bank.java", definition["start_line"], None,
                                  "error", "compiler_error", "synthetic measured diagnostic")
    measured = RepairScope("complete", "bank.java", member,
        members=(RepairMember("bank.java", member, "function", definition["start_line"],
                              definition["end_line"], definition["content"], (diagnostic,)),),
        evidence_fingerprint="1" * 64, source_fingerprint=hashlib.sha256(raw).hexdigest(),
        repository_id=inputs["repository_id"], control_fingerprint="2" * 64)
    if not authoring:
        return measured
    preflight = dict(evidence_source="PREFLIGHT.REQUEST.1", evidence_kind="compile_evidence",
        measured=True, ran=True, category="build_error", receipt_fingerprint=measured.evidence_fingerprint,
        control_sha256=measured.control_fingerprint, repository_id=measured.repository_id,
        source_fingerprints=[dict(path="bank.java", sha256=measured.source_fingerprint)],
        locations=[diagnostic.as_dict()], targets=[dict(path="bank.java", errors=1)])
    return AuthoringRepairScope(measured, ".", "java", source,
        ((definition["start"], definition["end"]),), (None,),
        json.dumps(preflight, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _targets(proposal, category=None):
    rows = (*proposal.existing_targets, *proposal.new_logical_targets)
    return {row.target for row in rows if category is None or row.category == category}


def _capabilities(proposal):
    return {row.code: row for row in proposal.required_capabilities}


def _assert_no_authority(result):
    assert result.candidate is None and result.patch == ""
    assert result.write_authority is result.execution_authorized is result.auto_apply is False
    assert result.model_calls == result.author_calls == result.repository_traversals == 0
    if result.proposal is not None:
        assert result.proposal.scope_authority == "proposal_only"
        assert result.proposal.write_authority is False


def test_complete_frozen_bank2_has_bounded_logical_expansion_without_candidate(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path)
    result = _call(inputs)
    assert inputs["detection"].status == "no_gap"
    assert result.status == "expansion_required"
    proposal = result.proposal
    assert proposal is not None
    assert proposal.current_edit_scope.status == "none"
    required = _targets(proposal, "MUST_CREATE_LOGICAL")
    assert "SavingAccount" in required and "SavingAccount::savingBalance" in required
    codes = _capabilities(proposal)
    assert {"new_subtype_definition", "subclass_owned_state", "subclass_initialization",
            "credential_state", "authentication_gated_savings_operation",
            "savings_funding_transition", "savings_interest_behavior"} <= set(codes)
    subtype = next(row for row in proposal.new_logical_targets if row.kind == "new_class")
    assert subtype.parent == "BankAccount" and subtype.file is None
    assert all(row.file is None for row in proposal.new_logical_targets)
    _assert_no_authority(result)


def test_measured_private_base_source_records_conditional_void_withdraw_insufficiency(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)
    result = _call(inputs)
    assert result.status == "expansion_required"
    proposal = result.proposal
    base = _capabilities(proposal)["base_balance_debit"]
    assert base.certainty == "MUST_SUPPORT"
    api_rows = [row for row in proposal.existing_targets
                if row.category == "MAY_REQUIRE_EXISTING_API_CHANGE"]
    assert api_rows and all(row.owner == "BankAccount" and row.api_surface for row in api_rows)
    explanation = proposal.to_json().casefold()
    assert "private" in explanation and "void" in explanation
    assert "success" in explanation and "conditional" in explanation
    assert all(row.kind != "existing_field" for row in api_rows)
    assert "protected balance" not in explanation and "public balance" not in explanation
    assert inputs["current_source"] == MEASURED_BANK.encode("utf-8")
    _assert_no_authority(result)


@pytest.mark.parametrize("answer_name", ["auth_only", "savings_only", "persistent_auth"])
def test_partial_bank2_never_creates_expansion_proposal(tmp_path, answer_name):
    inputs = fixture_inputs(repository_root=tmp_path, answer_name=answer_name)
    result = _call(inputs)
    assert inputs["detection"].status == "clarification_required"
    assert result.status == "semantic_intent_unresolved" and result.proposal is None
    _assert_no_authority(result)


def test_review_only_bank1_is_not_applicable(tmp_path):
    inputs = _base_inputs(tmp_path, "Review BankAccount and explain its existing savings behavior.")
    result = _call(inputs)
    assert result.status == "not_applicable" and result.proposal is None
    _assert_no_authority(result)


@pytest.mark.parametrize("authoring", [False, True])
def test_same_member_gate_fits_exact_current_scope(tmp_path, authoring):
    inputs = _typed_gate_inputs(tmp_path)
    scope = _repair(inputs, authoring=authoring)
    result = _call(inputs, current_scope=scope, expected_scope_fingerprint=scope_fingerprint(scope))
    assert result.status == "scope_expansion_not_required" and result.proposal is None
    _assert_no_authority(result)


def test_explicit_new_method_requires_definition_expansion_without_write_authority(tmp_path):
    inputs = _typed_gate_inputs(tmp_path, members=("BankAccount::secureDeposit",))
    result = _call(inputs)
    assert result.status == "expansion_required"
    target = next(row for row in result.proposal.new_logical_targets
                  if row.target == "BankAccount::secureDeposit")
    assert target.kind == "new_method_required" and target.category == "MUST_CREATE_LOGICAL"
    _assert_no_authority(result)


def test_explicit_new_subclass_uses_logical_target_and_defers_constructor_and_layout(tmp_path):
    inputs = _base_inputs(tmp_path, "SavingAccount extends BankAccount.")
    result = _call(inputs)
    assert result.status == "expansion_required"
    proposal = result.proposal
    assert "SavingAccount" in _targets(proposal, "MUST_CREATE_LOGICAL")
    assert "subclass_initialization" in _capabilities(proposal)
    choices = " ".join(item.decision for item in proposal.deferred_decisions).casefold()
    assert "constructor" in choices and "layout" in choices
    assert "SavingAccount.java" not in proposal.to_json()
    _assert_no_authority(result)


@pytest.mark.parametrize("method", [
    "public boolean withdraw(double amount) { if (balance >= amount) { balance -= amount; return true; } return false; }",
    "public void withdraw(double amount) { balance -= amount; }",
])
def test_exact_success_exposing_or_unconditional_debit_avoids_unnecessary_api_expansion(tmp_path, method):
    source = MEASURED_BANK.replace(
        "public void withdraw(double amount) {\n    if (amount <= balance) { balance -= amount; }\n  }", method)
    inputs = fixture_inputs(repository_root=tmp_path, source=source)
    result = _call(inputs)
    assert result.status == "expansion_required"
    assert not [row for row in result.proposal.existing_targets
                if row.category == "MAY_REQUIRE_EXISTING_API_CHANGE"]
    assert _capabilities(result.proposal)["base_balance_debit"].certainty == "MUST_SUPPORT"
    assert any("::withdraw: sufficient;" in evidence.fact for evidence in result.proposal.evidence)
    _assert_no_authority(result)


def test_two_already_acquired_classes_have_bounded_cross_class_scope(tmp_path):
    inputs = _typed_gate_inputs(tmp_path, members=("BankAccount::deposit", "Ledger::record"))
    context, raw = _context("class Ledger { public void record(double amount) {} }",
                            inputs["repository_id"], owner="Ledger", file="Ledger.java")
    result = _call(inputs, related_contexts=((context, raw),))
    assert result.status == "expansion_required"
    assert {"BankAccount::deposit", "Ledger::record"} <= _targets(result.proposal, "MUST_EDIT_EXISTING")
    assert "cross-class" in result.proposal.blast_radius
    _assert_no_authority(result)


def test_named_unacquired_related_class_stops_with_evidence_need(tmp_path):
    inputs = _typed_gate_inputs(tmp_path, members=("BankAccount::deposit", "Ledger::record"))
    result = _call(inputs)
    assert result.status == "scope_evidence_incomplete" and result.proposal is None
    assert "Ledger" in json.dumps(result.as_dict())
    _assert_no_authority(result)


def test_existing_saving_transition_preserves_equivalent_options_and_semantic_recheck(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)
    proposal = _call(inputs).proposal
    transition = next(item for item in proposal.deferred_decisions
                      if item.target == "BankAccount::saving")
    assert {"retirement", "override", "relocation", "compatibility_preservation"} <= set(transition.alternatives)
    assert transition.semantic_recheck_if_behavior_changes is True
    assert "existing_savings_transition" in _capabilities(proposal)
    assert not [row for row in proposal.existing_targets
                if row.target == "BankAccount::saving" and row.category == "MUST_EDIT_EXISTING"]


def test_final_base_saving_is_an_implementation_constraint_with_semantic_recheck_deferred(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path,
        source=MEASURED_BANK.replace("public void saving", "public final void saving"))
    result = _call(inputs)
    assert result.status == "expansion_required"
    assert "BankAccount::savings_transition_capability" in _targets(
        result.proposal, "MAY_REQUIRE_EXISTING_API_CHANGE")
    transition = next(item for item in result.proposal.deferred_decisions
                      if item.decision == "existing_savings_transition")
    assert transition.semantic_recheck_if_behavior_changes is True
    _assert_no_authority(result)


def test_final_base_class_requires_existing_inheritability_authority(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path,
        source=MEASURED_BANK.replace("class BankAccount", "final class BankAccount"))
    result = _call(inputs)
    assert result.status == "expansion_required"
    assert "BankAccount::inheritability" in _targets(result.proposal, "MUST_EDIT_EXISTING")
    assert _capabilities(result.proposal)["base_inheritability"].certainty == "MUST_SUPPORT"
    _assert_no_authority(result)


def test_private_only_base_construction_path_remains_a_possible_api_requirement(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path,
        source=MEASURED_BANK.replace("BankAccount(String", "private BankAccount(String"))
    result = _call(inputs)
    assert result.status == "expansion_required"
    assert "BankAccount::subclass_initialization_capability" in _targets(
        result.proposal, "MAY_REQUIRE_EXISTING_API_CHANGE")
    assert any(item.decision == "base_constructor_access_path_and_layout_evidence"
               for item in result.proposal.deferred_decisions)
    _assert_no_authority(result)


def test_overloaded_member_authority_does_not_cover_unmeasured_overload(tmp_path):
    source = MEMBER_BANK.replace(
        "public void deposit(double amount) { balance += amount; }",
        "public void deposit(double amount) { balance += amount; }\n"
        "  public void deposit(int amount) { balance += amount; }")
    inputs = _typed_gate_inputs(tmp_path, source=source)
    scope = _repair(inputs)
    result = _call(inputs, current_scope=scope, expected_scope_fingerprint=scope_fingerprint(scope))
    assert result.status == "expansion_required"
    targets = [t for t in result.proposal.existing_targets if t.target == "BankAccount::deposit"]
    assert len(targets) == 2
    assert len({t.declaration_fingerprint for t in targets}) == 2
    assert all(t.member_span for t in targets)
    assert len(scope.members) == 1
    _assert_no_authority(result)


def test_duplicate_simple_class_names_do_not_replace_exact_parent_evidence(tmp_path):
    inputs = _base_inputs(tmp_path, "SavingAccount extends BankAccount.")
    context, raw = _context("class Outer { static class BankAccount {} }",
        inputs["repository_id"], file="Outer.java")
    assert context.class_identity.qualified_name == "Outer.BankAccount"
    result = _call(inputs, related_contexts=((context, raw),))
    assert result.status == "scope_evidence_incomplete" and result.proposal is None
    _assert_no_authority(result)


def test_two_exact_classes_from_conflicting_versions_of_one_file_are_rejected(tmp_path):
    inputs = _typed_gate_inputs(tmp_path, members=("BankAccount::deposit", "Ledger::record"))
    context, raw = _context("class Ledger { public void record(double amount) {} }",
        inputs["repository_id"], owner="Ledger", file="bank.java")
    result = _call(inputs, related_contexts=((context, raw),))
    assert result.status == "invalid_proposal" and result.proposal is None
    assert "inconsistent_acquired_source_versions" in result.reasons
    _assert_no_authority(result)


def test_exact_source_mismatch_requires_reacquisition(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path)
    result = _call(inputs, current_source=inputs["current_source"] + b"\n// changed source")
    assert result.status == "reacquisition_required" and result.proposal is None
    _assert_no_authority(result)


def test_stale_effective_design_is_rejected_against_frozen_detection(tmp_path):
    complete = fixture_inputs(repository_root=tmp_path)
    partial = fixture_inputs(repository_root=tmp_path, answer_name="auth_only")
    result = _call(complete, design_intent=partial["design_intent"])
    assert result.status == "invalid_proposal" and result.proposal is None
    _assert_no_authority(result)


@pytest.mark.parametrize("field,value", [
    ("task_contract_fingerprint", "0" * 64), ("design_fingerprint", "0" * 64),
    ("repository_id", "forged-repository"), ("source_fingerprint", "0" * 64),
])
def test_detection_binding_mismatches_never_produce_scope(tmp_path, field, value):
    inputs = fixture_inputs(repository_root=tmp_path)
    result = _call(inputs, semantic_detection=replace(inputs["detection"], **{field: value}))
    assert result.status in {"invalid_proposal", "reacquisition_required"}
    assert result.proposal is None
    _assert_no_authority(result)


@pytest.mark.parametrize("forge", ["fingerprint", "source", "member", "repository", "missing_fingerprint"])
def test_forged_current_scope_is_rejected_without_mutation(tmp_path, forge):
    inputs = fixture_inputs(repository_root=tmp_path)
    scope = _repair(inputs)
    expected = scope_fingerprint(scope)
    if forge == "fingerprint":
        expected = "0" * 64
    elif forge == "source":
        scope = replace(scope, source_fingerprint="0" * 64)
        expected = scope_fingerprint(scope)
    elif forge == "member":
        scope = replace(scope, members=(replace(scope.members[0], source_snippet="forged member"),))
        expected = scope_fingerprint(scope)
    elif forge == "repository":
        scope = replace(scope, repository_id="wrong-repository")
        expected = scope_fingerprint(scope)
    else:
        expected = None
    before = scope.as_dict()
    result = _call(inputs, current_scope=scope, expected_scope_fingerprint=expected)
    assert result.status == ("reacquisition_required" if forge == "source" else "invalid_proposal")
    assert result.proposal is None
    assert scope.as_dict() == before
    _assert_no_authority(result)


def test_current_scope_snapshot_lists_exact_members_without_widening_it(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path)
    scope = _repair(inputs)
    before = scope.as_dict()
    before_design = inputs["design_intent"].as_dict()
    before_context = inputs["current_context"].as_dict()
    result = _call(inputs, current_scope=scope, expected_scope_fingerprint=scope_fingerprint(scope))
    assert result.status == "expansion_required"
    current = result.proposal.current_edit_scope
    assert current.status == "method_local"
    assert current.fingerprint == scope_fingerprint(scope)
    assert "deposit" in json.dumps(current.as_dict())
    assert scope.as_dict() == before
    assert inputs["design_intent"].as_dict() == before_design
    assert inputs["current_context"].as_dict() == before_context
    _assert_no_authority(result)


def test_same_inputs_have_same_immutable_serialization_and_fingerprint(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)
    first = _call(inputs).proposal
    second = _call(inputs).proposal
    assert first.as_dict() == second.as_dict()
    assert first.to_json() == second.to_json() and first.fingerprint == second.fingerprint
    assert hashlib.sha256(first.to_json().encode("utf-8")).hexdigest() == first.fingerprint
    with pytest.raises(FrozenInstanceError):
        first.status = "approved"
    with pytest.raises(FrozenInstanceError):
        first.new_logical_targets[0].target = "Elsewhere"
    detached = first.as_dict()
    detached["new_logical_targets"][0]["target"] = "Elsewhere"
    assert first.new_logical_targets[0].target != "Elsewhere"


def test_detection_timing_observations_do_not_change_proposal_identity(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path)
    first = _call(inputs).proposal
    detection = replace(inputs["detection"], total_seconds=123.0,
                        projection_validation_seconds=12.0)
    second = _call(inputs, semantic_detection=detection).proposal
    assert first.to_json() == second.to_json() and first.fingerprint == second.fingerprint


def test_forged_no_gap_cannot_bypass_material_semantic_clarification(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path, answer_name="auth_only")
    forged = replace(inputs["detection"], status="no_gap", possible_intent_gaps=())
    result = _call(inputs, semantic_detection=forged)
    assert result.status == "invalid_proposal" and result.proposal is None
    _assert_no_authority(result)


def test_every_scope_target_and_capability_has_bound_provenance(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)
    proposal = _call(inputs).proposal
    rows = (*proposal.required_capabilities, *proposal.existing_targets, *proposal.new_logical_targets)
    assert rows and all(row.evidence_refs for row in rows)
    payload = proposal.to_json()
    assert "explicit_human" in payload and "current_source_fact" in payload
    assert "validated_continuation" in payload
    assert inputs["design_intent"].fingerprint in payload
    assert inputs["current_context"].source_fingerprint in payload
    assert inputs["repository_id"] in payload


def test_phase_performs_no_model_author_traversal_execution_or_file_access(tmp_path, monkeypatch):
    inputs = fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)

    def forbidden(*args, **kwargs):
        raise AssertionError("proposal phase crossed its read-only in-memory boundary")

    monkeypatch.setattr(os, "walk", forbidden)
    monkeypatch.setattr(os, "scandir", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr("core.semantic_waiter_adapter.SemanticWaiterModelAdapter._complete", forbidden)
    result = _call(inputs)
    assert result.status == "expansion_required"
    _assert_no_authority(result)


def test_phase_reports_each_local_measurement_without_provider_latency(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path)
    timings = {}
    result = _call(inputs, timings=timings)
    assert result.status == "expansion_required"
    assert set(timings) == {"semantic_ready_validation_seconds", "structural_comparison_seconds",
                            "expansion_classification_seconds", "proposal_serialization_seconds", "total_seconds"}
    assert all(value >= 0 for value in timings.values())
    _assert_no_authority(result)


@pytest.mark.parametrize("field", ["balance_visibility", "withdraw_result", "class_parent"])
def test_forged_current_structure_is_rejected_even_when_source_digest_matches(tmp_path, field):
    inputs = fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)
    context = inputs["current_context"]
    if field == "balance_visibility":
        context = replace(context, fields=tuple(replace(item, visibility="protected")
                            if item.name == "balance" else item for item in context.fields))
    elif field == "withdraw_result":
        context = replace(context, methods=tuple(replace(item, return_type="boolean")
                            if item.name == "withdraw" else item for item in context.methods))
    else:
        context = replace(context, class_identity=replace(context.class_identity, extends="InventedBase"))
    result = _call(inputs, current_context=context)
    assert result.status == "invalid_proposal" and result.proposal is None
    _assert_no_authority(result)


@pytest.mark.parametrize("method", [
    "public boolean withdraw(double amount) { if (balance >= amount) { balance -= amount; } return true; }",
    "public boolean withdraw(double amount) { if (balance >= amount) { balance += amount; return true; } return false; }",
    "private boolean withdraw(double amount) { if (balance >= amount) { balance -= amount; return true; } return false; }",
])
def test_unproven_or_inaccessible_success_result_does_not_claim_transfer_support(tmp_path, method):
    source = MEASURED_BANK.replace(
        "public void withdraw(double amount) {\n    if (amount <= balance) { balance -= amount; }\n  }", method)
    result = _call(fixture_inputs(repository_root=tmp_path, source=source))
    assert result.status == "expansion_required"
    assert [row for row in result.proposal.existing_targets
            if row.category == "MAY_REQUIRE_EXISTING_API_CHANGE"]
    assert not any("::withdraw: sufficient;" in evidence.fact for evidence in result.proposal.evidence)
    _assert_no_authority(result)


def test_savings_state_and_credential_targets_do_not_select_types_or_exact_apis(tmp_path):
    proposal = _call(fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)).proposal
    savings = next(row for row in proposal.new_logical_targets if row.target == "SavingAccount::savingBalance")
    assert savings.kind == "new_field_required"
    credentials = [row for row in proposal.new_logical_targets if "credential" in row.target]
    assert credentials and all(row.kind == "capability" for row in credentials)
    assert not [row for row in proposal.new_logical_targets if row.name in {"password", "verifyPassword", "authenticate", "login"}]
    decisions = " ".join(item.decision for item in proposal.deferred_decisions).casefold()
    assert "type" in decisions and "visibility" in decisions and "signature" in decisions
    assert "layout" in decisions
    assert proposal.logical_creation_required is True
    assert proposal.write_authority is proposal.repair_scope_authority is proposal.apply_authority is False


def test_all_target_provenance_resolves_to_the_exact_evidence_table(tmp_path):
    proposal = _call(fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)).proposal
    references = {row.reference for row in proposal.evidence}
    for row in (*proposal.required_capabilities, *proposal.existing_targets, *proposal.new_logical_targets):
        assert set(row.evidence_refs) <= references
    changed = replace(proposal.new_logical_targets[0], evidence_refs=("explicit_human:" + "0" * 64,))
    with pytest.raises(ValueError, match="unbound_target_evidence"):
        replace(proposal, new_logical_targets=(changed, *proposal.new_logical_targets[1:]))


@pytest.mark.parametrize("field,limit", [
    ("source_bindings", expansion.MAX_CONTEXTS),
    ("required_capabilities", expansion.MAX_CAPABILITIES),
    ("existing_targets", expansion.MAX_EXISTING_TARGETS),
    ("new_logical_targets", expansion.MAX_NEW_TARGETS),
    ("deferred_decisions", expansion.MAX_DEFERRED_ITEMS),
    ("reasons", expansion.MAX_REASONS),
    ("evidence", expansion.MAX_EVIDENCE),
])
def test_immutable_proposal_collection_bounds_fail_without_truncation(tmp_path, field, limit):
    proposal = _call(fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)).proposal
    item = getattr(proposal, field)[0]
    with pytest.raises(ValueError, match="bound_exceeded"):
        replace(proposal, **{field: (item,) * (limit + 1)})
    with pytest.raises(ValueError, match="bound_exceeded"):
        replace(proposal, **{field: [item]})


def test_api_change_count_and_serialized_bytes_have_independent_bounds(tmp_path):
    proposal = _call(fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)).proposal
    api = next(row for row in proposal.existing_targets if row.category == "MAY_REQUIRE_EXISTING_API_CHANGE")
    with pytest.raises(ValueError, match="api_requirements_bound_exceeded"):
        replace(proposal, existing_targets=(api,) * (expansion.MAX_API_REQUIREMENTS + 1))
    evidence = (*proposal.evidence,)
    wide = tuple(replace(evidence[0], fact="x" * 512)
                 for _ in range(expansion.MAX_EVIDENCE - len(evidence)))
    with pytest.raises(ValueError, match="serialized_bytes_bound_exceeded"):
        replace(proposal, evidence=(*evidence, *wide))


def test_extra_acquired_contexts_overflow_stops_without_partial_proposal(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path)
    related = ((inputs["current_context"], inputs["current_source"]),) * expansion.MAX_CONTEXTS
    result = _call(inputs, related_contexts=related)
    assert result.status == "bounded" and result.proposal is None
    assert "related_contexts_bound_exceeded" in result.reasons
    _assert_no_authority(result)


def test_proposal_revalidation_binds_exact_scope_source_design_and_repository(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path)
    proposal = _call(inputs).proposal
    arguments = dict(task_contract=inputs["task_contract"], design_intent=inputs["design_intent"],
        semantic_detection=inputs["detection"], current_context=inputs["current_context"],
        current_source=inputs["current_source"], repository_id=inputs["repository_id"])
    expansion.validate_structural_scope_expansion_proposal(proposal, **arguments)
    changes = (dict(current_source=inputs["current_source"] + b"\n// stale"),
               dict(repository_id="other-repository"),
               dict(design_intent=fixture_inputs(repository_root=tmp_path,
                                                answer_name="auth_only")["design_intent"]),
               dict(current_scope=_repair(inputs), expected_scope_fingerprint=scope_fingerprint(_repair(inputs))))
    for overrides in changes:
        with pytest.raises(expansion.ScopeExpansionError, match="stale_or_invalid_proposal"):
            expansion.validate_structural_scope_expansion_proposal(proposal, **{**arguments, **overrides})


def test_proposal_cannot_be_consumed_as_authoring_scope(tmp_path):
    inputs = fixture_inputs(repository_root=tmp_path)
    proposal = _call(inputs).proposal
    result = _call(inputs, current_scope=proposal, expected_scope_fingerprint=proposal.fingerprint)
    assert result.status == "invalid_proposal" and result.proposal is None
    _assert_no_authority(result)
