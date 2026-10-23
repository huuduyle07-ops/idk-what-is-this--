"""Synthetic approvals only; exact-path acquisition and pure narrowing regressions."""
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.structural_scope_admission import (
    AdmissionError, TIMING_FIELDS, acquire_structural_admission_evidence,
    admit_structural_authoring_scope, validate_admitted_structural_authoring_scope,
)
from core.structural_implementation_plan import PlanError, build_structural_implementation_plan
from core.structural_scope_approval import decide_structural_scope_ceiling
from core.repair_scope import RepairScope
from scripts.replay_patch_scope_plan1 import approved_fixture, synthetic_planner_proposal
from tests.test_patch_scope_recheck1 import MEASURED_BANK

TRANSITIONS = ("savings_only_on_subclass", "preserve_base_compatibility", "subclass_specialization")


def make_case(root, transition=TRANSITIONS[0], *, source=MEASURED_BANK, path="SavingAccount.java", nested=False):
    root.mkdir(parents=True, exist_ok=True)
    inputs, action, receipt = approved_fixture(transition, root=root, source=source)
    (root / "bank.java").write_bytes(inputs["current_source"])
    proposal = synthetic_planner_proposal(inputs, receipt, path=path, nested=nested)
    plan = build_structural_implementation_plan(approval_receipt=receipt, stored_human_action=action,
                                               planner_output=proposal, **inputs)
    evidence = acquire_structural_admission_evidence(plan, repository_root=root, **inputs)
    return inputs, action, receipt, plan, evidence, root


@pytest.fixture(scope="module")
def cases(tmp_path_factory):
    root = tmp_path_factory.mktemp("admit1_synthetic")
    result = {t: make_case(root / t, t) for t in TRANSITIONS}
    private = MEASURED_BANK.replace("BankAccount(String", "private BankAccount(String", 1)
    result["nested"] = make_case(root / "nested", TRANSITIONS[1], source=private, path="bank.java", nested=True)
    return result


def admit(case, **changes):
    inputs, action, receipt, plan, evidence, _ = case
    return admit_structural_authoring_scope(**{**inputs, "plan": plan, "approval_receipt": receipt,
        "stored_human_action": action, "repository_evidence": evidence, **changes})


def validate(scope, case, **changes):
    inputs, action, receipt, plan, evidence, _ = case
    return validate_admitted_structural_authoring_scope(scope, **{**inputs, "plan": plan,
        "approval_receipt": receipt, "stored_human_action": action, "repository_evidence": evidence, **changes})


@pytest.mark.parametrize("transition", TRANSITIONS)
def test_each_transition_admits_exact_plan_with_no_write_authority(cases, transition):
    case = cases[transition]
    inputs, action, receipt, plan, evidence, root = case
    before = inputs["current_source"], receipt.as_dict(), inputs["current_scope"]
    timings = {}
    scope = admit(case, timings=timings)
    assert validate(json.loads(scope.to_json()), case) == scope
    assert admit(case).fingerprint == scope.fingerprint
    assert set(timings) == set(TIMING_FIELDS) and all(v >= 0 for v in timings.values())
    assert scope.scope_authority == "candidate_authoring_only" and scope.candidate_authoring_allowed
    assert scope.write_authority is scope.apply_authority is scope.execution_authorized is scope.auto_apply is False
    assert scope.filesystem_file_creation_authority is False
    assert scope.repair_scope_delta == scope.authoring_scope_delta == 0
    assert scope.candidate is None and scope.patch == ""
    assert scope.model_calls == scope.author_calls == scope.repository_traversals == 0
    assert scope.implementation_plan_fingerprint == plan.fingerprint
    assert scope.approval_receipt_fingerprint == receipt.fingerprint
    assert scope.current_scope_fingerprint == plan.current_scope_fingerprint
    assert scope.current_repair_scope_fingerprint == plan.current_repair_scope_fingerprint
    assert {a.approved_target for a in scope.definition_allowances} == set(plan.planner_proposal.selected_targets)
    assert not {a.approved_target for a in scope.definition_allowances} & set(plan.planner_proposal.ceiling_targets_not_used)
    assert scope.capability_coverage == plan.planner_proposal.capability_coverage
    assert len(scope.capability_coverage) == 9
    assert scope.implementation_decisions == plan.planner_proposal.implementation_decisions
    assert scope.savings_credit_guard == "successful_inherited_debit"
    assert len(scope.new_file_creation_targets) == 1
    new = scope.new_file_creation_targets[0]
    assert new.physical_target == "SavingAccount.java" and new.absence_witness.state == "absent"
    assert new.candidate_may_propose_new_file and not new.filesystem_file_creation_authority
    assert not (root / "SavingAccount.java").exists()
    assert new.definition_ids == tuple(sorted(a.definition.identity for a in scope.definition_allowances
                                              if a.definition.owner == "SavingAccount"))
    with pytest.raises(FrozenInstanceError):
        scope.status = "writable"
    assert before == (inputs["current_source"], receipt.as_dict(), inputs["current_scope"])


def test_unused_private_constructor_may_is_discarded_and_nested_layout_follows_plan(cases):
    case = cases["nested"]
    scope = admit(case)
    unused = next(t for t in case[3].planner_proposal.ceiling_targets_not_used
                  if t.name == "subclass_initialization_capability")
    assert not scope.new_file_creation_targets
    assert unused not in {a.approved_target for a in scope.definition_allowances}
    nested = next(o for o in scope.existing_file_authoring_targets if o.operation == "insert_nested_class")
    assert nested.physical_target == "bank.java" and nested.owner == "BankAccount"
    assert nested.class_body.declaration.owner == "BankAccount"
    assert len(nested.definition_ids) == 7
    assert all(o.operation != "modify_declaration" for o in scope.permitted_structural_operations)
    assert validate(scope, case) == scope


def test_selected_may_realizes_only_planned_member_insertion(cases):
    case = cases[TRANSITIONS[0]]
    scope = admit(case)
    insertion = next(o for o in scope.existing_file_authoring_targets if o.operation == "insert_member")
    assert insertion.definition_ids == ("BankAccount::debitForSavings::method",)
    definition = next(a.definition for a in scope.definition_allowances if a.definition.identity in insertion.definition_ids)
    assert definition.visibility == "protected" and definition.declared_type == "boolean"
    assert definition.parameters == (("double", "amount"),)
    assert insertion.existing_declaration is None and insertion.declaration_byte_span is None
    start, end = insertion.class_body.body_span
    assert case[0]["current_source"][start:start+1] == b"{"
    assert case[0]["current_source"][end-1:end] == b"}"
    assert insertion.class_body.body_fingerprint == sha256(case[0]["current_source"][start:end]).hexdigest()


def test_subclass_only_removal_is_exact_and_neighbors_stay_read_only(cases):
    case = cases[TRANSITIONS[0]]
    scope = admit(case)
    removal = next(o for o in scope.existing_file_authoring_targets if o.operation == "remove_declaration")
    assert removal.existing_declaration.name == "saving"
    binding = removal.existing_declaration
    start, end = removal.declaration_byte_span
    snippet = case[0]["current_source"][start:end].decode().replace("\r\n", "\n").replace("\r", "\n")
    assert sha256(snippet.encode()).hexdigest() == binding.declaration_fingerprint
    support = {r.declaration.name for r in scope.read_only_supporting_targets}
    assert {"BankAccount", "balance", "withdraw"} <= support and "saving" not in support
    assert all(r.authority == "read_only_support" for r in scope.read_only_supporting_targets)
    assert len(scope.existing_file_authoring_targets) == 2


@pytest.mark.parametrize("transition", TRANSITIONS[1:])
def test_preserved_base_saving_has_only_read_authority(cases, transition):
    scope = admit(cases[transition])
    assert any(r.declaration.name == "saving" for r in scope.read_only_supporting_targets)
    assert not any(o.existing_declaration and o.existing_declaration.name == "saving"
                   for o in scope.existing_file_authoring_targets)
    assert len(scope.existing_file_authoring_targets) == 1


def test_validation_tests_and_commands_are_evidence_only(cases):
    scope = admit(cases[TRANSITIONS[0]])
    assert any(n.proposed_test_file == "SavingAccountBehaviorTest.java" for n in scope.validation_evidence_needs)
    assert all(n.test_write_authority is False for n in scope.validation_evidence_needs)
    assert any(n.kind == "javac" for n in scope.validation_evidence_needs)
    assert all(o.physical_target != "SavingAccountBehaviorTest.java" for o in scope.permitted_structural_operations)
    assert scope.execution_authorized is False


@pytest.mark.parametrize("decision", ("decline_scope_expansion", "request_scope_revision"))
def test_decline_and_revision_never_supply_admission_authority(cases, decision):
    case = cases[TRANSITIONS[0]]
    action = replace(case[1], decision=decision)
    receipt = decide_structural_scope_ceiling(**case[0], human_action=action)
    with pytest.raises(AdmissionError, match="admission_unavailable"):
        admit(case, approval_receipt=receipt, stored_human_action=action)


@pytest.mark.parametrize("change", ("source", "context", "scope", "p1", "receipt", "task", "design", "repository", "action"))
def test_full_freshness_and_independent_approval_gate(cases, change):
    case = cases[TRANSITIONS[0]]
    inputs = case[0]
    changes = {
        "source": {"current_source": inputs["current_source"] + b"\n// changed"},
        "context": {"current_context": replace(inputs["current_context"], source_fingerprint="changed")},
        "scope": {"current_scope": RepairScope("not_applicable", "bank.java", "saving")},
        "p1": {"proposal": cases[TRANSITIONS[1]][0]["proposal"]},
        "receipt": {"approval_receipt": cases[TRANSITIONS[1]][2]},
        "task": {},
        "design": {"scope_transition_effective_design": cases[TRANSITIONS[1]][0]["scope_transition_effective_design"]},
        "repository": {"repository_id": cases[TRANSITIONS[1]][0]["repository_id"]},
        "action": {"stored_human_action": None},
    }
    if change == "task":
        from core.input_understanding import understand_request
        changes["task"] = {"task_contract": understand_request("A different task")}
    with pytest.raises(AdmissionError):
        admit(case, **changes[change])


@pytest.mark.parametrize("field", ("status", "plan_fingerprint", "current_scope_fingerprint", "write_authority"))
def test_forged_plan_labels_hashes_and_authority_are_reconstructed(cases, field):
    case = cases[TRANSITIONS[0]]
    payload = case[3].as_dict()
    payload[field] = True if field == "write_authority" else "forged"
    with pytest.raises(AdmissionError, match="admission_stale"):
        admit(case, plan=payload)


@pytest.mark.parametrize("field", ("write_authority", "execution_authorized", "apply_authority", "auto_apply",
                                   "filesystem_file_creation_authority"))
def test_authority_escalation_is_invalid_even_with_recomputed_hash(cases, field):
    case = cases[TRANSITIONS[0]]
    payload = admit(case).as_dict()
    payload[field] = True
    payload["admission_fingerprint"] = "forged"
    with pytest.raises(AdmissionError, match="admission_authority_escalation"):
        validate(payload, case)


@pytest.mark.parametrize("extra", ("Database", "UserRepository", "AccountSession", "UnplannedHelper"))
def test_extra_definition_cannot_recover_ceiling_authority(cases, extra):
    case = cases[TRANSITIONS[0]]
    payload = admit(case).as_dict()
    row = json.loads(json.dumps(payload["definition_allowances"][0]))
    row["definition"].update(owner=extra, name=extra, definition_id=extra)
    payload["definition_allowances"].append(row)
    with pytest.raises(AdmissionError, match="admission_outside_validated_plan"):
        validate(payload, case)


@pytest.mark.parametrize("field", ("existing_file_authoring_targets", "permitted_structural_operations", "new_file_creation_targets"))
def test_wider_structural_envelopes_fail_closed(cases, field):
    case = cases[TRANSITIONS[0]]
    payload = admit(case).as_dict()
    payload[field][0]["operation" if field != "new_file_creation_targets" else "owner"] = "replace_whole_class"
    with pytest.raises(AdmissionError, match="admission_scope_nonminimal"):
        validate(payload, case)


def test_unapproved_test_file_and_read_support_cannot_enter_edit_set(cases):
    case = cases[TRANSITIONS[1]]
    payload = admit(case).as_dict()
    payload["permitted_structural_operations"].append({"operation": "draft_new_file",
        "physical_target": "SavingAccountBehaviorTest.java"})
    with pytest.raises(AdmissionError, match="admission_scope_nonminimal"):
        validate(payload, case)
    payload = admit(case).as_dict()
    payload["read_only_supporting_targets"][0]["authority"] = "editable"
    with pytest.raises(AdmissionError, match="admission_outside_validated_plan"):
        validate(payload, case)


def test_new_path_collision_before_and_after_admission_is_rechecked(tmp_path):
    case = make_case(tmp_path)
    scope = admit(case)
    before = scope.to_json()
    (tmp_path / "SavingAccount.java").write_text("occupied", encoding="utf-8")
    evidence = acquire_structural_admission_evidence(case[3], repository_root=tmp_path, **case[0])
    with pytest.raises(AdmissionError, match="admission_conflict_existing_path"):
        admit(case, repository_evidence=evidence)
    with pytest.raises(AdmissionError, match="admission_conflict_existing_path"):
        validate(scope, case, repository_evidence=evidence)
    assert scope.to_json() == before
    assert (tmp_path / "SavingAccount.java").read_text() == "occupied"


def test_actual_disk_source_change_cannot_hide_behind_old_supplied_buffer(tmp_path):
    case = make_case(tmp_path)
    scope = admit(case)
    (tmp_path / "bank.java").write_bytes(case[0]["current_source"] + b"\n// changed")
    evidence = acquire_structural_admission_evidence(case[3], repository_root=tmp_path, **case[0])
    with pytest.raises(AdmissionError, match="reacquisition_required"):
        validate(scope, case, repository_evidence=evidence)


def test_different_valid_plan_cannot_reuse_an_admission(cases):
    case = cases[TRANSITIONS[0]]
    scope = admit(case)
    proposal = synthetic_planner_proposal(case[0], case[2], helper_name="tryDebit")
    plan = build_structural_implementation_plan(approval_receipt=case[2], stored_human_action=case[1],
                                               planner_output=proposal, **case[0])
    with pytest.raises(AdmissionError, match="admission_stale"):
        validate(scope, case, plan=plan)


@pytest.mark.parametrize("path", ("../SavingAccount.java", "/SavingAccount.java", "C:/SavingAccount.java",
                                  "safe\\SavingAccount.java", "safe//SavingAccount.java", "SavingAccount.txt"))
def test_acquisition_does_not_normalize_unsafe_paths(cases, path):
    case = cases[TRANSITIONS[0]]
    plan = replace(case[3], planner_proposal=replace(case[3].planner_proposal,
        logical_creations=tuple(replace(m, proposed_physical_target=path) for m in case[3].planner_proposal.logical_creations)))
    with pytest.raises(AdmissionError, match="admission_outside_repository_policy"):
        acquire_structural_admission_evidence(plan, repository_root=case[5], **case[0])


@pytest.mark.parametrize("directory", (".tmp", ".temp", ".agent", "build", "dist", "target", "node_modules"))
def test_hard_excluded_paths_are_rejected_before_package_mapping(tmp_path, directory):
    if directory == ".agent":
        with pytest.raises(PlanError, match="plan_outside_approved_ceiling"):
            make_case(tmp_path, path=directory + "/SavingAccount.java")
        return
    case = make_case(tmp_path, path=directory + "/SavingAccount.java")
    with pytest.raises(AdmissionError, match="admission_outside_repository_policy"):
        admit(case)


@pytest.mark.parametrize("policy", (".gitignore", ".cattusignore"))
def test_ignore_policy_is_measured_and_revalidated(tmp_path, policy):
    case = make_case(tmp_path)
    scope = admit(case)
    (tmp_path / policy).write_text("SavingAccount.java\n", encoding="utf-8")
    evidence = acquire_structural_admission_evidence(case[3], repository_root=tmp_path, **case[0])
    with pytest.raises(AdmissionError, match="admission_outside_repository_policy"):
        validate(scope, case, repository_evidence=evidence)


def test_unestablished_package_directory_is_incomplete(tmp_path):
    case = make_case(tmp_path, path="education/SavingAccount.java")
    with pytest.raises(AdmissionError, match="scope_evidence_incomplete"):
        admit(case)


def test_symlink_escape_exact_path_is_rejected_without_walk(tmp_path):
    case = make_case(tmp_path / "repo", path="linked/SavingAccount.java")
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (case[5] / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        # Windows hosts without symlink privilege still exercise the actual
        # containment primitive deterministically, without skipping the test.
        original = Path.resolve
        def resolve(path, *args, **kwargs):
            if path.name == "linked":
                return outside
            return original(path, *args, **kwargs)
        with patch.object(Path, "resolve", resolve), pytest.raises(AdmissionError, match="symlink escape"):
            acquire_structural_admission_evidence(case[3], repository_root=case[5], **case[0])
    else:
        with pytest.raises(AdmissionError, match="symlink escape"):
            acquire_structural_admission_evidence(case[3], repository_root=case[5], **case[0])


def test_pure_admission_and_future_validator_have_zero_effects(cases):
    case = cases[TRANSITIONS[0]]
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected provider, author, execution, I/O or traversal")
    guards = ("core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "core.control_engine.build_control_prompt", "core.control_engine.authoring_context_for_control_result",
        "socket.create_connection", "subprocess.run", "subprocess.Popen", "os.system", "os.walk", "os.scandir",
        "os.listdir", "pathlib.Path.open", "pathlib.Path.read_bytes", "pathlib.Path.write_bytes",
        "pathlib.Path.write_text", "builtins.open")
    with ExitStack() as stack:
        for target in guards:
            stack.enter_context(patch(target, forbidden))
        scope = admit(case)
        assert validate(scope, case) == scope


def test_exact_path_acquisition_never_walks_or_writes(cases):
    case = cases[TRANSITIONS[0]]
    with ExitStack() as stack:
        for target in ("os.walk", "os.scandir", "os.listdir", "pathlib.Path.write_bytes", "pathlib.Path.write_text"):
            stack.enter_context(patch(target, side_effect=AssertionError("walk/write forbidden")))
        evidence = acquire_structural_admission_evidence(case[3], repository_root=case[5], **case[0])
    assert evidence == case[4]


def test_missing_or_extra_path_evidence_fails_closed(cases):
    case = cases[TRANSITIONS[0]]
    with pytest.raises(AdmissionError, match="scope_evidence_incomplete"):
        admit(case, repository_evidence=replace(case[4], paths=case[4].paths[:-1]))
    with pytest.raises(AdmissionError, match="scope_evidence_incomplete"):
        admit(case, repository_evidence=case[4].__dict__ if hasattr(case[4], "__dict__") else {})


def test_changed_policy_even_when_permissive_invalidates_historical_admission(tmp_path):
    case = make_case(tmp_path)
    scope = admit(case)
    (tmp_path / ".gitignore").write_text("# policy changed\n", encoding="utf-8")
    evidence = acquire_structural_admission_evidence(case[3], repository_root=tmp_path, **case[0])
    with pytest.raises(AdmissionError, match="admission_stale"):
        validate(scope, case, repository_evidence=evidence)


def test_unused_may_cannot_be_recovered_by_scope_transport(cases):
    case = cases["nested"]
    payload = admit(case).as_dict()
    unused = next(t for t in case[3].planner_proposal.ceiling_targets_not_used
                  if t.name == "subclass_initialization_capability")
    from dataclasses import asdict
    payload["permitted_structural_operations"].append({"operation": "modify_declaration",
        "physical_target": "bank.java", "owner": "BankAccount", "approved_targets": [asdict(unused)]})
    with pytest.raises(AdmissionError, match="admission_scope_nonminimal"):
        validate(payload, case)


def test_definition_signature_visibility_and_contract_are_frozen(cases):
    case = cases[TRANSITIONS[0]]
    scope = admit(case)
    payload = scope.as_dict()
    allowance = next(a for a in payload["definition_allowances"] if a["definition"]["name"] == "debitForSavings")
    allowance["definition"]["visibility"] = "public"
    allowance["definition"]["parameters"] = []
    allowance["definition"]["contract"] = "unrelated_structure"
    # A valid hash of a forged scope still cannot substitute for reconstruction.
    payload["admission_fingerprint"] = sha256(json.dumps({k: v for k, v in payload.items()
        if k != "admission_fingerprint"}, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(AdmissionError, match="admission_outside_validated_plan"):
        validate(payload, case)


def test_scope_and_path_evidence_reject_transitively_mutable_fields(cases):
    case = cases[TRANSITIONS[0]]
    scope = admit(case)
    with pytest.raises(AdmissionError, match="mutable authority/evidence field"):
        replace(scope, definition_allowances=list(scope.definition_allowances))
    with pytest.raises(AdmissionError, match="mutable authority/evidence field"):
        replace(case[4], paths=list(case[4].paths))


@pytest.mark.parametrize("authoring", (False, True))
def test_exact_prior_measured_or_authoring_scope_is_bound_without_mutation(tmp_path, authoring):
    from dataclasses import asdict
    from core.structural_scope_expansion import propose_structural_scope_expansion, scope_fingerprint
    from core.structural_scope_refresh import refresh_structural_scope_proposal
    from core.scope_semantic_recheck import (
        recheck_scope_semantics, make_stored_scope_transition_gap, continue_scope_transition,
        compose_scope_transition_design,
    )
    from core.oop_intent_session import bind_human_answer
    from core.structural_scope_approval import HumanScopeDecisionAction, prepare_structural_scope_review
    from scripts.replay_patch_scope_expand1 import fixture_inputs
    from scripts.replay_patch_scope_refresh1 import ANSWERS
    from tests.test_patch_scope_expand1 import _repair
    base = fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)
    prior = _repair(base, member="withdraw", authoring=authoring)
    before = asdict(prior)
    parent = dict(task_contract=base["task_contract"], design_intent=base["design_intent"],
        semantic_detection=base["detection"], current_context=base["current_context"],
        current_source=base["current_source"], repository_id=base["repository_id"],
        current_scope=prior, expected_scope_fingerprint=scope_fingerprint(prior), related_contexts=())
    p0 = propose_structural_scope_expansion(**parent).proposal
    recheck_inputs = dict(proposal=p0, **parent, repo_path=base["repo_path"],
        stored_gap=base["stored_gap"], stored_answer=base["stored_answer"])
    gap = make_stored_scope_transition_gap(recheck_scope_semantics(**recheck_inputs),
        task_contract=base["task_contract"], current_context=base["current_context"], repository_id=base["repository_id"])
    answer = bind_human_answer(gap, ANSWERS[TRANSITIONS[0]]).as_dict()
    continuation = continue_scope_transition(**recheck_inputs, stored_transition_gap=gap, stored_transition_answer=answer)
    recheck = recheck_scope_semantics(**recheck_inputs, transition_continuation=continuation,
        stored_transition_gap=gap, stored_transition_answer=answer)
    args = dict(task_contract=base["task_contract"], historical_proposal=p0, repo_path=base["repo_path"],
        original_design_intent=base["base_design"], continue1_continuation=base["continuation"],
        original_stored_gap=base["stored_gap"], original_stored_answer=base["stored_answer"],
        original_semantic_detection=base["detection"], transition_continuation=continuation,
        current_context=base["current_context"], current_source=base["current_source"],
        repository_id=base["repository_id"], current_scope=prior,
        expected_scope_fingerprint=scope_fingerprint(prior), related_contexts=(),
        stored_transition_gap=gap, stored_transition_answer=answer,
        scope_transition_effective_design=compose_scope_transition_design(base["design_intent"], continuation),
        validated_recheck_receipt=recheck)
    refresh = refresh_structural_scope_proposal(**args)
    inputs = dict(args, proposal=refresh.proposal, refresh_result=refresh)
    review = prepare_structural_scope_review(**inputs)
    action = HumanScopeDecisionAction("approve_exact_scope_ceiling", review.proposal.fingerprint,
        review.fingerprint, "explicit_human", "synthetic_human_action")
    receipt = decide_structural_scope_ceiling(**inputs, human_action=action)
    plan = build_structural_implementation_plan(approval_receipt=receipt, stored_human_action=action,
        planner_output=synthetic_planner_proposal(inputs, receipt), **inputs)
    (tmp_path / "bank.java").write_bytes(inputs["current_source"])
    evidence = acquire_structural_admission_evidence(plan, repository_root=tmp_path, **inputs)
    case = inputs, action, receipt, plan, evidence, tmp_path
    scope = admit(case)
    assert scope.current_scope_fingerprint == scope_fingerprint(prior)
    assert scope.current_repair_scope_fingerprint == plan.current_repair_scope_fingerprint
    assert validate(scope, case) == scope
    assert asdict(prior) == before
    with pytest.raises(AdmissionError, match="admission_stale"):
        validate(scope, case, current_scope=None)


def test_explicit_package_and_directory_evidence_admits_only_matching_path(tmp_path):
    import scripts.replay_patch_scope_expand1 as expand_replay
    original = expand_replay.project_class_semantic_context
    def packaged(**kwargs):
        return original(**{**kwargs, "file": "edu/bank.java"})
    source = "package edu;\n" + MEASURED_BANK
    with patch.object(expand_replay, "project_class_semantic_context", packaged):
        inputs, action, receipt = approved_fixture(root=tmp_path, source=source)
    (tmp_path / "edu").mkdir()
    (tmp_path / "edu/bank.java").write_bytes(inputs["current_source"])
    plan = build_structural_implementation_plan(approval_receipt=receipt, stored_human_action=action,
        planner_output=synthetic_planner_proposal(inputs, receipt, path="edu/SavingAccount.java"), **inputs)
    evidence = acquire_structural_admission_evidence(plan, repository_root=tmp_path, **inputs)
    scope = admit((inputs, action, receipt, plan, evidence, tmp_path))
    assert scope.new_file_creation_targets[0].package_name == "edu"
    assert not (tmp_path / "edu/SavingAccount.java").exists()
