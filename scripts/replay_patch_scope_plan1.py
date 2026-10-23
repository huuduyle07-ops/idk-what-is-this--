"""Synthetic PLAN.1 governance replay. No real BANK.2 approval is consumed."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.structural_implementation_plan import (
    TIMING_FIELDS, CapabilityCoverage, ImplementationDecision, MayTargetSelection,
    PlanTargetIdentity, PlannedDefinition, PlannedTarget, PlannerProposal,
    ValidationEvidenceNeed, build_structural_implementation_plan, declaration_bindings,
    validate_structural_implementation_plan, PlanError,
)
from core.structural_scope_approval import (
    HumanScopeDecisionAction, decide_structural_scope_ceiling, prepare_structural_scope_review,
)
from core.structural_scope_refresh import refresh_structural_scope_proposal
from scripts.replay_patch_scope_expand1 import fixture_inputs
from scripts.replay_patch_scope_refresh1 import _scenario, ANSWERS


def approved_fixture(transition="savings_only_on_subclass", *, root=None, source=None, decision="approve_exact_scope_ceiling"):
    original = fixture_inputs(repository_root=root, source=source)
    args = _scenario(original, ANSWERS[transition])[-1]
    refresh = refresh_structural_scope_proposal(**args)
    inputs = dict(proposal=refresh.proposal, refresh_result=refresh, **args)
    review = prepare_structural_scope_review(**inputs)
    action = HumanScopeDecisionAction(decision, review.proposal.fingerprint, review.fingerprint,
        "explicit_human", "synthetic_human_action")
    receipt = decide_structural_scope_ceiling(**inputs, human_action=action)
    return inputs, action, receipt


def synthetic_planner_proposal(inputs, receipt, *, path="SavingAccount.java", nested=False, helper_name="debitForSavings"):
    """One illustrative planner choice, deliberately outside harness policy.

    Other layouts, constructors, names and internal API shapes are legal. This
    fixture chooses a protected boolean helper and a private String credential.
    """
    ceiling = receipt.approved_scope_ceiling
    identities = {t.target: PlanTargetIdentity.of(t) for t in (*ceiling.new_logical_targets, *ceiling.existing_targets)}
    declarations = declaration_bindings(inputs)
    transition = inputs["scope_transition_effective_design"].existing_savings_transition
    logical, existing = [], []
    context = inputs["current_context"]
    base_ctor = context.explicit_constructors[0]
    ctor_parameters = tuple((p.declared_type, p.name) for p in base_ctor.parameters) + (("String", "password"),)
    base_saving = next(m for m in context.methods if m.name == "saving")
    interest_parameters = tuple((p.declared_type, p.name) for p in base_saving.parameters)
    def definition(owner, name, kind, visibility, dtype, roles, contract, parameters=(), parent=None):
        d = PlannedDefinition(owner, name, kind, visibility, dtype, parameters, parent, roles, contract)
        return d
    def creation(key, definitions):
        logical.append(PlannedTarget(identities[key], path, not nested, "create", tuple(definitions), (),
            "Required logical capability is implemented by the proposed definition", "nested_in_parent" if nested else "top_level"))
    creation("SavingAccount", [
        definition("SavingAccount", "SavingAccount", "class", "public", "", ("new_subtype_definition",),
            "inherits_approved_parent", parent="BankAccount"),
        definition("SavingAccount", "SavingAccount", "constructor", "public", "", ("subclass_initialization",),
            "compatible_base_constructor_initialization", ctor_parameters)])
    creation("SavingAccount::savingBalance", [definition("SavingAccount", "savingBalance", "field", "private", "double",
        ("subclass_owned_state",), "subclass_owned_savings_state")])
    creation("SavingAccount::credential_state_and_verification", [definition("SavingAccount", "password", "field", "private", "String",
        ("credential_state",), "simple_in_memory_password")])
    creation("SavingAccount::authentication_gated_savings_capability", [
        definition("SavingAccount", "verifySavingsPassword", "method", "private", "boolean",
            ("authentication_gated_savings_operation",), "operation_gated_password_verification", (("String", "providedPassword"),)),
        definition("SavingAccount", "transferToSavings", "method", "public", "boolean",
            ("savings_funding_transition",), "credit_only_after_successful_inherited_debit", (("double", "amount"), ("String", "providedPassword")))])
    interest_name = "saving" if transition == "subclass_specialization" else "accrueSavingsInterest"
    creation("SavingAccount::savings_interest_behavior", [definition("SavingAccount", interest_name, "method", "public", "void",
        ("savings_interest_behavior",), "interest_on_saving_balance_only", interest_parameters)])
    debit_key = "BankAccount::successful_balance_debit_capability"
    if debit_key in identities:
        d = definition("BankAccount", helper_name, "method", "protected", "boolean", ("base_balance_debit",),
            "observable_atomic_successful_debit", (("double", "amount"),))
        existing.append(PlannedTarget(identities[debit_key], identities[debit_key].file, False,
            "add_internal_capability", (d,), (), "Current void withdrawal has no observable success result for an atomic transfer"))
    if transition == "savings_only_on_subclass":
        binding = next(b for b in declarations if b.owner == "BankAccount" and b.name == "saving")
        d = definition("BankAccount", "saving", "method", "public", "void", ("existing_savings_transition",),
            "retire_base_savings_from_intended_api", interest_parameters)
        existing.append(PlannedTarget(identities["BankAccount::saving"], binding.file, False, "remove", (d,),
            (binding,), "Subclass-only savings requires retirement of current base behavior"))
    coverage = []
    for capability in ceiling.required_capabilities:
        if capability.certainty != "MUST_SUPPORT":
            continue
        planned = tuple(d.identity for m in (*logical, *existing) for d in m.definitions if capability.code in d.roles)
        mechanisms = ()
        if not planned:
            name = "withdraw" if capability.code == "base_balance_debit" else "saving"
            mechanisms = (next(b for b in declarations if b.owner == "BankAccount" and b.name == name),)
        coverage.append(CapabilityCoverage(capability.code, capability.target, planned, mechanisms,
            "Required semantic capability has a concrete implementation or sufficient current declaration"))
    selected = tuple(m.approved_target for m in (*logical, *existing))
    decisions = (
        ("source_layout", "SavingAccount", "Static nested class inside BankAccount" if nested else "Separate top-level Java source at the proposed path"),
        ("constructor", "SavingAccount", "Initialize inherited holder and balance through super construction and store the supplied credential"),
        ("state", "SavingAccount::savingBalance", "Private double savingBalance initialized to zero"),
        ("credential", "SavingAccount::credential_state_and_verification", "Private String password with a private equality-check helper before each savings operation"),
        ("debit", debit_key if debit_key in identities else "SavingAccount", "Protected boolean debit helper" if debit_key in identities else "Reuse proven existing observable debit"),
        ("savings_funding", "SavingAccount::authentication_gated_savings_capability", "Verify first and credit savingBalance only after successful inherited debit"),
        ("savings_interest", "SavingAccount::savings_interest_behavior", "Verify each operation and apply the current simple interest calculation only to savingBalance"),
        ("existing_saving_transition", "BankAccount::saving", "Remove current base savings behavior" if transition == "savings_only_on_subclass"
            else "Preserve base behavior and specialize the common contract" if transition == "subclass_specialization" else "Preserve current base saving behavior unchanged"),
    )
    design = inputs["scope_transition_effective_design"]
    return PlannerProposal(selected, tuple(logical), tuple(existing), tuple(ImplementationDecision(area,
        identities[key], choice, "This code shape preserves the supplied semantic commitment") for area, key, choice in decisions),
        tuple(MayTargetSelection(t, next(m.reason for m in existing if m.approved_target == t))
              for t in selected if t.category == "MAY_REQUIRE_EXISTING_API_CHANGE"),
        tuple(t for t in identities.values() if t not in selected), tuple(coverage),
        tuple((x.dimension, x.value) for x in design.parent.continuation.typed_answer_commitments) +
            (("existing_savings_transition", transition),), ("in_memory",), (),
        "successful_inherited_debit", "encapsulated",
        "remove" if transition == "savings_only_on_subclass" else "preserve_and_specialize" if transition == "subclass_specialization" else "preserve",
        transition == "subclass_specialization", ("One bounded implementation proposal inside the approved ceiling",),
        (ValidationEvidenceNeed("javac", identities["SavingAccount"], "Compile the proposed classes during later authorized implementation", None),
         ValidationEvidenceNeed("validation_evidence_need", identities["SavingAccount"],
            "Later behavioral evidence should cover failed verification, unsuccessful debit, transfer conservation and the chosen base transition", "SavingAccountBehaviorTest.java")),
        None, 0.85)


def replay(*, repetitions=5):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    scenarios = {}
    for transition in ANSWERS:
        inputs, action, receipt = approved_fixture(transition)
        scenarios[transition] = (inputs, action, receipt, synthetic_planner_proposal(inputs, receipt))
    original = fixture_inputs()["current_source"].decode()
    private_source = original.replace("BankAccount(", "private BankAccount(", 1)
    inputs, action, receipt = approved_fixture("preserve_base_compatibility", source=private_source)
    scenarios["unused_MAY_nested_layout"] = (inputs, action, receipt,
        synthetic_planner_proposal(inputs, receipt, path="bank.java", nested=True))
    guards = ("core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "core.control_engine.build_control_prompt", "core.control_engine.authoring_context_for_control_result",
        "socket.create_connection", "socket.socket.connect", "subprocess.run", "subprocess.Popen", "os.system",
        "os.walk", "os.scandir", "os.listdir", "pathlib.Path.open", "pathlib.Path.read_bytes", "pathlib.Path.read_text",
        "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open")
    def forbidden(*_a, **_kw):
        raise AssertionError("PLAN.1 attempted provider, author, execution, file I/O or traversal")
    results, negative_results = {}, {}
    with ExitStack() as stack:
        for target in guards:
            stack.enter_context(patch(target, forbidden))
        for name, (inputs, action, receipt, proposal) in scenarios.items():
            before = inputs["current_source"], receipt.as_dict(), inputs["proposal"].as_dict()
            samples, fingerprints = [], []
            for _ in range(repetitions):
                timings = {}
                plan = build_structural_implementation_plan(approval_receipt=receipt, stored_human_action=action,
                    planner_output=proposal, timings=timings, **inputs)
                assert validate_structural_implementation_plan(plan.as_dict(), approval_receipt=receipt,
                    stored_human_action=action, **inputs) == plan
                assert plan.candidate is None and plan.patch == "" and not plan.write_authority
                samples.append(timings)
                fingerprints.append(plan.fingerprint)
            assert len(set(fingerprints)) == 1
            assert before == (inputs["current_source"], receipt.as_dict(), inputs["proposal"].as_dict())
            results[name] = {"plan": plan.as_dict(), "deterministic": True,
                "source_bytes_unchanged": True, "source_fingerprint": sha256(inputs["current_source"]).hexdigest(),
                "performance": {key: {"median_ms": round(statistics.median(x[key] for x in samples)*1000, 6),
                    "max_ms": round(max(x[key] for x in samples)*1000, 6)} for key in TIMING_FIELDS}}
        inputs, action, receipt, proposal = scenarios["savings_only_on_subclass"]
        broad = replace(proposal.selected_targets[0], target="UserRepository")
        public_debit = replace(proposal, existing_modifications=tuple(replace(m, definitions=tuple(
            replace(d, visibility="public") if "base_balance_debit" in d.roles else d for d in m.definitions))
            for m in proposal.existing_modifications))
        decline_action = replace(action, decision="decline_scope_expansion")
        decline_receipt = decide_structural_scope_ceiling(**inputs, human_action=decline_action)
        negatives = {
            "outside_ceiling": ({"planner_output": replace(proposal, selected_targets=(*proposal.selected_targets, broad))}, "plan_outside_approved_ceiling"),
            "missing_authentication_MUST": ({"planner_output": replace(proposal, capability_coverage=tuple(
                c for c in proposal.capability_coverage if c.code != "authentication_gated_savings_operation"))}, "plan_incomplete"),
            "database_invention": ({"planner_output": replace(proposal, infrastructure=("database",))}, "plan_semantic_drift"),
            "new_lockout_policy": ({"planner_output": replace(proposal, new_semantic_policies=("three_attempts_then_lockout",))}, "plan_semantic_drift"),
            "stale_source": ({"current_source": inputs["current_source"] + b"\n// stale"}, "reacquisition_required"),
            "wrong_transition_receipt": ({"approval_receipt": scenarios["subclass_specialization"][2]}, "planning_stale"),
            "declined_ceiling": ({"approval_receipt": decline_receipt, "stored_human_action": decline_action}, "planning_unavailable"),
            "public_debit_nonminimal": ({"planner_output": public_debit}, "plan_scope_nonminimal"),
            "new_material_question": ({"planner_output": replace(proposal, unresolved_plan_issue="A new material semantic choice needs a human answer")}, "semantic_clarification_required"),
            "patch_output": ({"planner_output": {**proposal.as_dict(), "patch": "diff --git"}}, "plan_output_contains_patch"),
        }
        for name, (changes, expected) in negatives.items():
            try:
                build_structural_implementation_plan(**{**inputs, "approval_receipt": receipt,
                    "stored_human_action": action, "planner_output": proposal, **changes})
            except PlanError as exc:
                assert exc.code == expected, (name, exc.code)
                negative_results[name] = {"status": exc.code, "plan": None, "candidate": None, "patch": ""}
            else:
                raise AssertionError((name, "unsafe plan accepted"))
    return {"phase_id": "PATCH.SCOPE.PLAN.1", "fixture_kind": "synthetic_approved_receipts_and_typed_planner_outputs",
        "scenarios": results, "negative_cases": negative_results, "repetitions": repetitions, "model_calls": 0, "author_calls": 0,
        "repository_traversals": 0, "real_BANK2_approval_consumed": False, "source_bytes_unchanged": True,
        "MainApp_session_touched": False, "candidate": None, "patch": "", "repair_scope_delta": 0,
        "authoring_scope_delta": 0, "write_authority": False, "apply_authority": False,
        "execution_authorized": False, "provider_latency": "not_applicable_no_live_provider",
        "first_remaining_blocker": "SCOPE_ADMISSION_NOT_IMPLEMENTED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    options = parser.parse_args()
    result = replay(repetitions=options.repetitions)
    if options.output:
        options.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"phase_id": result["phase_id"], "scenarios": {k: {"fingerprint": v["plan"]["plan_fingerprint"],
        "performance": v["performance"]} for k, v in result["scenarios"].items()},
        "first_remaining_blocker": result["first_remaining_blocker"]}, indent=2))
