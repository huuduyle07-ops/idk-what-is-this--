"""Synthetic approved P1 and planner proposals; no real session is consumed."""
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
from time import sleep
from unittest.mock import patch

import pytest

from core.structural_implementation_plan import (
    TIMING_FIELDS, PlanError, PlanTargetIdentity, PlannedDefinition,
    build_structural_implementation_plan, normalize_planner_proposal,
    plan_structural_implementation, prepare_structural_implementation_context,
    validate_structural_implementation_plan, validate_plan_ceiling_containment,
)
from core.structural_scope_approval import decide_structural_scope_ceiling
from scripts.replay_patch_scope_plan1 import approved_fixture, synthetic_planner_proposal
from tests.test_patch_scope_recheck1 import MEASURED_BANK


@pytest.fixture(scope="module")
def scenarios(tmp_path_factory):
    root = tmp_path_factory.mktemp("plan1_synthetic")
    result = {}
    for transition in ("savings_only_on_subclass", "preserve_base_compatibility", "subclass_specialization"):
        inputs, action, receipt = approved_fixture(transition, root=root, source=MEASURED_BANK)
        result[transition] = (inputs, action, receipt, synthetic_planner_proposal(inputs, receipt))
    private = MEASURED_BANK.replace("BankAccount(String", "private BankAccount(String", 1)
    inputs, action, receipt = approved_fixture("preserve_base_compatibility", root=root, source=private)
    result["unused_may"] = (inputs, action, receipt, synthetic_planner_proposal(inputs, receipt, path="bank.java", nested=True))
    return result


def _build(case, **overrides):
    inputs, action, receipt, output = case
    return build_structural_implementation_plan(**{**inputs, "approval_receipt": receipt,
        "stored_human_action": action, "planner_output": output, **overrides})


def _safe(value):
    assert value.authority == "read_only_plan"
    assert value.repair_scope_delta == value.authoring_scope_delta == 0
    assert value.candidate is None and value.patch == ""
    assert value.author_calls == value.repository_traversals == 0
    assert value.write_authority is value.execution_authorized is value.apply_authority is False


def _change_definition(proposal, definition_name, **changes):
    remap = {}
    def mapping(m):
        definitions = []
        for d in m.definitions:
            changed = replace(d, **changes) if d.name == definition_name else d
            remap[d.identity] = changed.identity
            definitions.append(changed)
        return replace(m, definitions=tuple(definitions))
    logical = tuple(mapping(m) for m in proposal.logical_creations)
    existing = tuple(mapping(m) for m in proposal.existing_modifications)
    coverage = tuple(replace(c, planned_definitions=tuple(remap[x] for x in c.planned_definitions))
                     for c in proposal.capability_coverage)
    return replace(proposal, logical_creations=logical, existing_modifications=existing, capability_coverage=coverage)


@pytest.mark.parametrize("transition", ("savings_only_on_subclass", "preserve_base_compatibility", "subclass_specialization"))
def test_each_transition_yields_immutable_exact_subset_read_only_plan(scenarios, transition):
    inputs, action, receipt, proposal = case = scenarios[transition]
    before = inputs["current_source"], receipt.as_dict(), inputs["proposal"].as_dict(), inputs["current_scope"]
    plan = _build(case)
    assert plan.status == "validated_read_only_plan"
    assert plan.p1_fingerprint == receipt.proposal_fingerprint
    assert plan.approval_receipt_fingerprint == receipt.fingerprint
    assert plan.approved_ceiling_fingerprint == receipt.approved_scope_ceiling_fingerprint
    assert plan.source_bindings == receipt.source_bindings
    assert validate_structural_implementation_plan(plan.as_dict(), approval_receipt=receipt,
        stored_human_action=action, **inputs) == plan
    assert validate_plan_ceiling_containment(plan.planner_proposal, receipt.approved_scope_ceiling,
        current_inputs=inputs)
    approved = {PlanTargetIdentity.of(x) for x in (*receipt.approved_scope_ceiling.new_logical_targets,
                                               *receipt.approved_scope_ceiling.existing_targets)}
    assert set(plan.planner_proposal.selected_targets) <= approved
    expected = {(c.code, c.target) for c in receipt.approved_scope_ceiling.required_capabilities if c.certainty == "MUST_SUPPORT"}
    assert {(c.code, c.target) for c in plan.planner_proposal.capability_coverage} == expected
    _safe(plan)
    with pytest.raises(FrozenInstanceError):
        plan.status = "authorized"
    assert before == (inputs["current_source"], receipt.as_dict(), inputs["proposal"].as_dict(), inputs["current_scope"])


def test_unused_approved_may_is_not_an_edit_checklist(scenarios):
    inputs, action, receipt, output = case = scenarios["unused_may"]
    plan = _build(case)
    unused = next(t for t in plan.planner_proposal.ceiling_targets_not_used
                  if t.name == "subclass_initialization_capability")
    assert unused.category == "MAY_REQUIRE_EXISTING_API_CHANGE"
    assert unused not in plan.planner_proposal.selected_targets
    assert all(x.target != unused for x in plan.planner_proposal.may_targets_selected)
    assert all(x.approved_target != unused for x in plan.planner_proposal.existing_modifications)
    assert all(not m.proposed_new_file and not m.file_creation_authority for m in plan.planner_proposal.logical_creations)
    assert plan.ceiling_targets_not_used_status == "ceiling_available_but_unused"


def test_layout_helpers_constructor_and_state_types_are_planner_owned(scenarios):
    inputs, action, receipt, output = case = scenarios["savings_only_on_subclass"]
    alternative = synthetic_planner_proposal(inputs, receipt, path="education/Savings.java", helper_name="tryDebit")
    alternative = _change_definition(alternative, "SavingAccount", visibility="package")
    alternative = _change_definition(alternative, "savingBalance", declared_type="Double")
    alternate_ctor = (("String", "password"), ("double", "balance"), ("String", "accountHolder"))
    # Both the class and constructor have this name, so replace just the constructor.
    mappings = list(alternative.logical_creations)
    first = mappings[0]
    ctor = next(d for d in first.definitions if d.kind == "constructor")
    new_ctor = replace(ctor, parameters=alternate_ctor)
    mappings[0] = replace(first, definitions=tuple(new_ctor if d is ctor else d for d in first.definitions))
    alternative = replace(alternative, logical_creations=tuple(mappings), capability_coverage=tuple(
        replace(c, planned_definitions=tuple(new_ctor.identity if x == ctor.identity else x for x in c.planned_definitions))
        for c in alternative.capability_coverage))
    plan = _build(case, planner_output=alternative)
    assert plan.fingerprint != _build(case).fingerprint
    assert all(m.proposed_physical_target == "education/Savings.java" for m in plan.planner_proposal.logical_creations)
    assert any(d.parameters == alternate_ctor for m in plan.planner_proposal.logical_creations for d in m.definitions)


def test_context_is_bounded_explicit_and_not_a_patch_prompt(scenarios):
    inputs, action, receipt, _ = scenarios["savings_only_on_subclass"]
    timings = {}
    context = prepare_structural_implementation_context(approval_receipt=receipt, stored_human_action=action,
        timings=timings, **inputs)
    data = context.payload
    assert "design planning only" in data["boundary"] and "Do not emit code or a patch" in data["boundary"]
    assert data["approved_p1_fingerprint"] == receipt.proposal_fingerprint
    assert data["repository_id"] == receipt.repository_id
    assert data["current_scope_fingerprint"] == receipt.current_scope_fingerprint
    assert data["resolved_transition"] == "savings_only_on_subclass"
    assert len(data["relevant_class_contexts"]) == 1
    assert data["relevant_class_contexts"][0]["exact_class_snippet"] == MEASURED_BANK
    assert data["deferred_choices"] and data["semantic_commitments"] and data["output_schema"]
    assert context.write_authority is False and len(context.context_json.encode()) <= 96_000
    data["approved_p1_fingerprint"] = "forged"
    assert context.payload["approved_p1_fingerprint"] == receipt.proposal_fingerprint


@pytest.mark.parametrize("target", ("BankAccount::balance", "database", "UserRepository", "UnrelatedClass", "SavingAccountExtra"))
def test_outside_ceiling_and_prefix_matches_are_rejected(scenarios, target):
    case = scenarios["savings_only_on_subclass"]
    output = case[3]
    forged = replace(output.selected_targets[0], target=target)
    with pytest.raises(PlanError, match="plan_outside_approved_ceiling"):
        _build(case, planner_output=replace(output, selected_targets=(forged, *output.selected_targets)))


@pytest.mark.parametrize("path", ("../SavingAccount.java", "C:/SavingAccount.java", "/SavingAccount.java",
    ".git/SavingAccount.java", "safe/../../SavingAccount.java", "safe\\SavingAccount.java", "safe//SavingAccount.java"))
def test_proposed_paths_cannot_be_write_envelopes(scenarios, path):
    case = scenarios["savings_only_on_subclass"]
    output = case[3]
    with pytest.raises(PlanError, match="plan_outside_approved_ceiling"):
        _build(case, planner_output=replace(output, logical_creations=tuple(
            replace(m, proposed_physical_target=path) for m in output.logical_creations)))


@pytest.mark.parametrize("code", ("authentication_gated_savings_operation", "savings_funding_transition", "base_balance_debit"))
def test_missing_must_is_incomplete(scenarios, code):
    case = scenarios["savings_only_on_subclass"]
    output = case[3]
    with pytest.raises(PlanError, match="plan_incomplete"):
        _build(case, planner_output=replace(output, capability_coverage=tuple(c for c in output.capability_coverage if c.code != code)))


@pytest.mark.parametrize("change", ("lockout", "database", "persistence", "funding", "public_balance", "semantic_commitment"))
def test_new_semantics_are_quarantined(scenarios, change):
    case = scenarios["savings_only_on_subclass"]
    output = case[3]
    if change == "lockout":
        output = replace(output, new_semantic_policies=("three_password_attempts_then_lockout",))
    elif change == "database":
        output = replace(output, infrastructure=("database",))
    elif change == "persistence":
        output = replace(output, infrastructure=("file_persistence",))
    elif change == "funding":
        output = replace(output, savings_credit_guard="unconditional_credit")
    elif change == "public_balance":
        output = replace(output, inherited_balance_access="public_field")
    else:
        output = replace(output, semantic_commitments=tuple((k, "database" if k == "credential_persistence" else v)
                                                          for k, v in output.semantic_commitments))
    with pytest.raises(PlanError, match="plan_semantic_drift"):
        _build(case, planner_output=output)


def test_free_text_cannot_hide_new_policy(scenarios):
    case = scenarios["savings_only_on_subclass"]
    with pytest.raises(PlanError, match="plan_semantic_drift"):
        _build(case, planner_output=replace(case[3], rationale=("Allow three password attempts then lockout",)))


@pytest.mark.parametrize("transition", ("preserve_base_compatibility", "subclass_specialization"))
def test_compatibility_and_specialization_cannot_remove_base_saving(scenarios, transition):
    case = scenarios[transition]
    with pytest.raises(PlanError, match="plan_semantic_drift"):
        _build(case, planner_output=replace(case[3], base_saving_action="remove"))


def test_subclass_only_cannot_preserve_current_base_savings_model(scenarios):
    case = scenarios["savings_only_on_subclass"]
    with pytest.raises(PlanError, match="plan_semantic_drift"):
        _build(case, planner_output=replace(case[3], base_saving_action="preserve"))


def test_specialization_requires_common_contract_and_compatible_definition(scenarios):
    case = scenarios["subclass_specialization"]
    for output, code in ((replace(case[3], common_savings_contract=False), "plan_semantic_drift"),
            (_change_definition(case[3], "saving", name="unrelatedInterest"), "plan_incomplete")):
        with pytest.raises(PlanError, match=code):
            _build(case, planner_output=output)


def test_public_base_debit_escalation_is_nonminimal(scenarios):
    case = scenarios["savings_only_on_subclass"]
    with pytest.raises(PlanError, match="plan_scope_nonminimal"):
        _build(case, planner_output=_change_definition(case[3], "debitForSavings", visibility="public"))


def test_redundant_definition_is_nonminimal(scenarios):
    case = scenarios["savings_only_on_subclass"]
    first, *rest = case[3].logical_creations
    extra = PlannedDefinition("SavingAccount", "SavingAccount", "constructor", "private", "", (), None,
        ("subclass_initialization",), "unneeded_helper")
    with pytest.raises(PlanError, match="plan_scope_nonminimal"):
        _build(case, planner_output=replace(case[3], logical_creations=(replace(first, definitions=(*first.definitions, extra)), *rest)))


def test_selected_may_needs_justification_and_coverage(scenarios):
    case = scenarios["savings_only_on_subclass"]
    for output in (replace(case[3], may_targets_selected=()),
                   replace(case[3], may_targets_selected=tuple(replace(x, reason="") for x in case[3].may_targets_selected))):
        with pytest.raises(PlanError):
            _build(case, planner_output=output)


def test_modified_declaration_binding_cannot_be_stale(scenarios):
    case = scenarios["savings_only_on_subclass"]
    mappings = tuple(replace(m, existing_declarations=tuple(replace(b, declaration_fingerprint="a"*64)
        for b in m.existing_declarations)) for m in case[3].existing_modifications)
    with pytest.raises(PlanError, match="plan_stale"):
        _build(case, planner_output=replace(case[3], existing_modifications=mappings))


@pytest.mark.parametrize("field", ("task", "source", "context", "design", "scope", "repository", "p1"))
def test_stale_inputs_fail_before_provider(scenarios, field):
    inputs, action, receipt, output = scenarios["savings_only_on_subclass"]
    bad = dict(inputs)
    if field == "task":
        bad["task_contract"] = scenarios["preserve_base_compatibility"][0]["task_contract"]
        bad["task_contract"] = replace(bad["task_contract"], raw_request=replace(
            bad["task_contract"].raw_request, text="Changed human task"))
    elif field == "source":
        bad["current_source"] += b"\n// changed"
    elif field == "context":
        bad["current_context"] = replace(inputs["current_context"], file="different.java")
    elif field == "design":
        bad["scope_transition_effective_design"] = scenarios["preserve_base_compatibility"][0]["scope_transition_effective_design"]
    elif field == "scope":
        from core.repair_scope import RepairScope
        bad["current_scope"] = RepairScope(status="not_applicable", primary_file="bank.java", primary_symbol="saving")
    elif field == "repository":
        bad["repository_id"] = "different_repo"
    else:
        bad["proposal"] = scenarios["preserve_base_compatibility"][0]["proposal"]
    provider = _Planner(output)
    result = plan_structural_implementation(approval_receipt=receipt, stored_human_action=action,
        planner=provider, planning_call_authorized=True, **bad)
    assert result.status in {"planning_stale", "reacquisition_required"}
    assert result.plan is None and provider.calls == result.model_calls == 0
    _safe(result)


@pytest.mark.parametrize("decision", ("decline_scope_expansion", "request_scope_revision"))
def test_nonapprove_receipts_disable_planning(scenarios, decision):
    inputs, action, _, output = scenarios["savings_only_on_subclass"]
    action = replace(action, decision=decision)
    receipt = decide_structural_scope_ceiling(**inputs, human_action=action)
    provider = _Planner(output)
    result = plan_structural_implementation(approval_receipt=receipt, stored_human_action=action,
        planner=provider, planning_call_authorized=True, **inputs)
    assert result.status == "planning_unavailable" and provider.calls == result.model_calls == 0


def test_historical_p0_wrong_receipt_or_frontend_boolean_cannot_enable_planning(scenarios):
    inputs, action, receipt, output = case = scenarios["savings_only_on_subclass"]
    for overrides in ({"approval_receipt": {"approved": True}}, {"stored_human_action": None},
            {"approval_receipt": scenarios["subclass_specialization"][2]},
            {"proposal": inputs["historical_proposal"]}):
        with pytest.raises(PlanError):
            _build(case, **overrides)


@pytest.mark.parametrize("key,value", (("patch", "diff --git"), ("candidate", {}), ("code", "class X {}"), ("commands", ["javac *"])))
def test_patch_output_is_quarantined(scenarios, key, value):
    case = scenarios["savings_only_on_subclass"]
    raw = case[3].as_dict()
    raw[key] = value
    with pytest.raises(PlanError, match="plan_output_contains_patch"):
        _build(case, planner_output=raw)


@pytest.mark.parametrize("code", ("```java\nclass SavingAccount {}\n```", "diff --git a/b b/b", "balance += amount;"))
def test_code_in_narrative_is_quarantined(scenarios, code):
    case = scenarios["savings_only_on_subclass"]
    with pytest.raises(PlanError, match="plan_output_contains_patch"):
        _build(case, planner_output=replace(case[3], rationale=(code,)))


def test_new_material_question_returns_to_clarification_without_resampling(scenarios):
    inputs, action, receipt, output = scenarios["savings_only_on_subclass"]
    provider = _Planner(replace(output, unresolved_plan_issue="Human must resolve a newly discovered externally meaningful account policy"))
    result = plan_structural_implementation(approval_receipt=receipt, stored_human_action=action,
        planner=provider, planning_call_authorized=True, **inputs)
    assert result.status == "semantic_clarification_required" and result.plan is None
    assert result.model_calls == provider.calls == 1
    _safe(result)


class _Planner:
    def __init__(self, output=None, error=False, latency=False):
        self.output, self.error, self.latency, self.calls = output, error, latency, 0

    def plan(self, context):
        self.calls += 1
        assert context.authority == "read_only_plan" and not context.write_authority
        if self.latency:
            sleep(0.025)
        if self.error:
            raise RuntimeError("private provider diagnostics")
        return self.output


@pytest.mark.parametrize("mode", ("valid", "invalid", "failure", "unavailable", "unauthorized"))
def test_single_authorized_planner_call_budget_and_typed_failures(scenarios, mode):
    inputs, action, receipt, output = scenarios["savings_only_on_subclass"]
    provider = None if mode == "unavailable" else _Planner(output if mode != "invalid" else {"bad": True}, mode == "failure")
    result = plan_structural_implementation(approval_receipt=receipt, stored_human_action=action,
        planner=provider, planning_call_authorized=mode != "unauthorized", **inputs)
    expected = {"valid": "validated_read_only_plan", "invalid": "plan_invalid_output",
        "failure": "planning_provider_failure", "unavailable": "planning_provider_unavailable",
        "unauthorized": "planning_call_not_authorized"}
    assert result.status == expected[mode]
    assert result.model_calls == (1 if mode in {"valid", "invalid", "failure"} else 0)
    assert provider is None or provider.calls == result.model_calls
    assert "private provider diagnostics" not in result.reason
    _safe(result)


def test_timing_separates_provider_latency_and_deterministic_overhead(scenarios):
    inputs, action, receipt, output = scenarios["savings_only_on_subclass"]
    timings = {}
    result = plan_structural_implementation(approval_receipt=receipt, stored_human_action=action,
        planner=_Planner(output, latency=True), planning_call_authorized=True, timings=timings, **inputs)
    assert result.plan and set(timings) == set(TIMING_FIELDS)
    assert timings["planner_call_seconds"] >= 0.025
    assert all(t >= 0 for t in timings.values())
    assert timings["total_deterministic_seconds"] >= timings["approval_validation_seconds"]


def test_normalization_determinism_does_not_reorder_constructor_parameters(scenarios):
    case = scenarios["savings_only_on_subclass"]
    raw = case[3].as_dict()
    for key in ("selected_targets", "logical_creations", "existing_modifications", "implementation_decisions",
                "capability_coverage", "semantic_commitments", "may_targets_selected", "required_validation"):
        raw[key].reverse()
    first = _build(case)
    second = _build(case, planner_output=raw)
    assert first.to_json() == second.to_json()
    assert first.fingerprint == second.fingerprint


@pytest.mark.parametrize("field,value", (("write_authority", True), ("apply_authority", 1), ("file_creation_authority", True),
    ("plan_fingerprint", "a"*64), ("task_fingerprint", "a"*64), ("approval_receipt_fingerprint", "a"*64),
    ("repair_scope_delta", 1), ("authoring_scope_delta", 1), ("status", "authorized")))
def test_later_admission_validator_rejects_forgery(scenarios, field, value):
    case = scenarios["savings_only_on_subclass"]
    inputs, action, receipt, _ = case
    payload = _build(case).as_dict()
    payload[field] = value
    with pytest.raises(PlanError, match="plan_stale"):
        validate_structural_implementation_plan(payload, approval_receipt=receipt, stored_human_action=action, **inputs)


def test_core_has_no_io_traversal_execution_or_author_calls(scenarios):
    case = scenarios["savings_only_on_subclass"]
    inputs, action, receipt, output = case
    before = inputs["current_source"], receipt.as_dict()
    targets = ("core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "core.control_engine.build_control_prompt", "core.control_engine.authoring_context_for_control_result",
        "socket.create_connection", "socket.socket.connect", "subprocess.run", "subprocess.Popen",
        "os.system", "os.walk", "os.scandir", "os.listdir", "pathlib.Path.open", "pathlib.Path.read_bytes",
        "pathlib.Path.read_text", "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open")
    def forbidden(*_a, **_kw):
        raise AssertionError("read-only PLAN.1 attempted effects")
    with ExitStack() as guards:
        for target in targets:
            guards.enter_context(patch(target, forbidden))
        plan = _build(case)
        validate_structural_implementation_plan(plan, approval_receipt=receipt, stored_human_action=action, **inputs)
        context = prepare_structural_implementation_context(approval_receipt=receipt, stored_human_action=action, **inputs)
        result = plan_structural_implementation(approval_receipt=receipt, stored_human_action=action,
            planner=_Planner(output), planning_call_authorized=True, **inputs)
    assert result.plan == plan and context.write_authority is False
    assert before == (inputs["current_source"], receipt.as_dict())
    _safe(plan)


def test_schema_bounds_unknown_keys_and_telemetry(scenarios):
    raw = scenarios["savings_only_on_subclass"][3].as_dict()
    for bad in ({**raw, "unknown": True}, {**raw, "confidence": True}, {**raw, "confidence": float("nan")},
                {**raw, "rationale": ["x"*70_000]}, {**raw, "selected_targets": [raw["selected_targets"][0]]*65}):
        with pytest.raises(PlanError, match="plan_invalid_output"):
            normalize_planner_proposal(bad)


def test_missing_required_logical_creation_and_unmapped_definitions(scenarios):
    case = scenarios["savings_only_on_subclass"]
    output = case[3]
    removed = next(m for m in output.logical_creations if m.approved_target.name == "savingBalance")
    incomplete = replace(output,
        logical_creations=tuple(m for m in output.logical_creations if m is not removed),
        selected_targets=tuple(t for t in output.selected_targets if t != removed.approved_target),
        ceiling_targets_not_used=(*output.ceiling_targets_not_used, removed.approved_target))
    with pytest.raises(PlanError, match="plan_incomplete"):
        _build(case, planner_output=incomplete)


def test_existing_void_withdrawal_is_not_a_successful_debit_proof(scenarios):
    from core.structural_implementation_plan import declaration_bindings
    case = scenarios["savings_only_on_subclass"]
    binding = next(x for x in declaration_bindings(case[0]) if x.name == "withdraw")
    output = case[3]
    output = replace(output, capability_coverage=tuple(replace(c, planned_definitions=(), existing_mechanisms=(binding,))
        if c.code == "base_balance_debit" else c for c in output.capability_coverage))
    with pytest.raises(PlanError, match="plan_incomplete"):
        _build(case, planner_output=output)


@pytest.mark.parametrize("change,code", (("declaration_type", "plan_output_contains_patch"),
    ("unapproved_type", "plan_outside_approved_ceiling"), ("new_file_flag", "plan_incomplete"),
    ("file_authority", "plan_invalid_output")))
def test_structured_fields_cannot_smuggle_code_infrastructure_or_authority(scenarios, change, code):
    case = scenarios["savings_only_on_subclass"]
    output = case[3].as_dict()
    if change == "declaration_type":
        output["logical_creations"][0]["definitions"][0]["declared_type"] = "void; public class Outside {}"
    elif change == "unapproved_type":
        output["logical_creations"][1]["definitions"][0]["declared_type"] = "UserRepository"
    elif change == "new_file_flag":
        output["logical_creations"][0]["proposed_new_file"] = False
    else:
        output["logical_creations"][0]["file_creation_authority"] = True
    with pytest.raises(PlanError, match=code):
        _build(case, planner_output=output)


def test_proposed_test_file_is_only_a_validation_evidence_need(scenarios):
    plan = _build(scenarios["savings_only_on_subclass"])
    test_need = next(x for x in plan.planner_proposal.required_validation if x.proposed_test_file)
    assert test_need.kind == "validation_evidence_need" and test_need.test_write_authority is False


def test_model_context_supplies_exact_ids_and_closed_nested_schema(scenarios):
    inputs, action, receipt, _ = scenarios["savings_only_on_subclass"]
    context = prepare_structural_implementation_context(approval_receipt=receipt, stored_human_action=action, **inputs).payload
    assert context["approved_target_identities"]
    assert "definition_id" in context["output_schema"]["PlannedDefinition"]
    assert "Choose unique local definition_id labels" in context["boundary"]
    assert set(context["output_schema"]) >= {"PlannerProposal", "PlannedTarget", "DeclarationBinding"}


def test_frozen_bookkeeping_restores_dirty_entry_hashes():
    from hashlib import sha256
    import json
    from pathlib import Path
    from tests._patch_scope_plan1_maintenance import before_patch_scope_plan1
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tests/fixtures/patch_scope_plan1_reversal.json").read_text())
    for row in receipt["reversals"]:
        restored = before_patch_scope_plan1(row["path"], (root / row["path"]).read_bytes())
        assert sha256(restored).hexdigest() == row["entry_sha256"]


def test_public_top_level_layout_must_be_source_compatible(scenarios):
    inputs, action, receipt, output = case = scenarios["savings_only_on_subclass"]
    incompatible = synthetic_planner_proposal(inputs, receipt, path="SomeOtherFile.java")
    with pytest.raises(PlanError, match="plan_incomplete"):
        _build(case, planner_output=incompatible)


def test_unknown_semantic_role_cannot_hide_in_a_definition(scenarios):
    case = scenarios["savings_only_on_subclass"]
    changed = _change_definition(case[3], "debitForSavings", roles=("base_balance_debit", "new_domain_policy"))
    with pytest.raises(PlanError, match="plan_semantic_drift"):
        _build(case, planner_output=changed)
