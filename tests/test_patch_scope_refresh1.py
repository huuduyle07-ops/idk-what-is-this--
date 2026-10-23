"""PATCH.SCOPE.REFRESH.1: re-propose after one validated human transition."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from core.oop_intent_session import bind_human_answer
from core.scope_semantic_recheck import (
    compose_scope_transition_design, continue_scope_transition,
    make_stored_scope_transition_gap, recheck_scope_semantics,
    recheck_refreshed_scope_semantics,
)
from core.structural_scope_expansion import scope_fingerprint
from core.structural_scope_refresh import (
    RefreshedStructuralScopeExpansionProposal,
    refresh_structural_scope_proposal,
)
from scripts.replay_patch_scope_expand1 import fixture_inputs
from tests.test_patch_scope_recheck1 import (
    MEASURED_BANK, TRANSITION_ANSWERS, _proposal, _recheck, _stored_gap,
)


def _chain(root, transition="savings_only_on_subclass", *, answer=None, source=None):
    Path(root).mkdir(parents=True, exist_ok=True)
    inputs = fixture_inputs(repository_root=root, source=source)
    p0 = _proposal(inputs)
    initial = _recheck(inputs, proposal=p0)
    gap = _stored_gap(inputs, initial)
    answer_text = TRANSITION_ANSWERS.get(transition, transition) if answer is None else answer
    answer_record = bind_human_answer(gap, answer_text).as_dict()
    continuation = continue_scope_transition(
        proposal=p0, task_contract=inputs["task_contract"],
        design_intent=inputs["design_intent"], semantic_detection=inputs["detection"],
        current_context=inputs["current_context"], current_source=inputs["current_source"],
        repository_id=inputs["repository_id"], repo_path=inputs["repo_path"],
        stored_gap=inputs["stored_gap"], stored_answer=inputs["stored_answer"],
        current_scope=None, expected_scope_fingerprint=None, related_contexts=(),
        stored_transition_gap=gap, stored_transition_answer=answer_record)
    effective = compose_scope_transition_design(inputs["design_intent"], continuation)
    receipt = recheck_scope_semantics(
        proposal=p0, task_contract=inputs["task_contract"],
        design_intent=inputs["design_intent"], semantic_detection=inputs["detection"],
        current_context=inputs["current_context"], current_source=inputs["current_source"],
        repository_id=inputs["repository_id"], repo_path=inputs["repo_path"],
        stored_gap=inputs["stored_gap"], stored_answer=inputs["stored_answer"],
        current_scope=None, expected_scope_fingerprint=None, related_contexts=(),
        transition_continuation=continuation, stored_transition_gap=gap,
        stored_transition_answer=answer_record)
    args = dict(
        historical_proposal=p0, task_contract=inputs["task_contract"],
        original_design_intent=inputs["base_design"],
        continue1_continuation=inputs["continuation"],
        original_stored_gap=inputs["stored_gap"],
        original_stored_answer=inputs["stored_answer"],
        original_semantic_detection=inputs["detection"],
        transition_continuation=continuation,
        scope_transition_effective_design=effective,
        validated_recheck_receipt=receipt,
        stored_transition_gap=gap, stored_transition_answer=answer_record,
        current_context=inputs["current_context"], current_source=inputs["current_source"],
        repository_id=inputs["repository_id"], repo_path=inputs["repo_path"],
        current_scope=None, expected_scope_fingerprint=None, related_contexts=())
    return inputs, args, continuation, effective, receipt


def _refresh(args, **overrides):
    return refresh_structural_scope_proposal(**{**args, **overrides})


def _target(proposal, name="BankAccount::saving"):
    return next(item for item in proposal.existing_targets if item.target == name)


def _transition_capability(proposal):
    return next(item for item in proposal.required_capabilities
                if item.code == "existing_savings_transition")


def _assert_proposal_only(result):
    assert result.status == "refreshed"
    assert isinstance(result.proposal, RefreshedStructuralScopeExpansionProposal)
    assert result.authority == result.scope_authority == "proposal_only"
    assert result.write_authority is result.execution_authorized is False
    assert result.auto_apply is result.apply_authority is result.repair_scope_authority is False
    assert result.repair_scope_delta == result.authoring_scope_delta == 0
    assert result.candidate is None and result.patch == ""
    assert result.author_calls == result.model_calls == result.repository_traversals == 0


@pytest.mark.parametrize("value", [
    "savings_only_on_subclass", "preserve_base_compatibility", "subclass_specialization",
])
def test_each_valid_transition_builds_bound_deterministic_proposal_and_fixpoint(tmp_path, value):
    inputs, args, continuation, effective, receipt = _chain(tmp_path, value)
    p0_json = args["historical_proposal"].to_json()
    result = _refresh(args)
    retry = _refresh(args)
    _assert_proposal_only(result)
    assert result.proposal.fingerprint == retry.proposal.fingerprint
    assert result.proposal.parent_proposal_fingerprint == args["historical_proposal"].fingerprint
    assert result.proposal.transition_continuation_fingerprint == continuation.fingerprint
    assert result.proposal.effective_design_fingerprint == effective.fingerprint
    assert result.proposal.repository_id == inputs["repository_id"]
    assert result.proposal.source_bindings == args["historical_proposal"].source_bindings
    assert result.proposal.refresh_reason == "semantic_transition_resolved"
    assert result.proposal.authority == result.proposal.scope_authority == "proposal_only"
    assert result.proposal.write_authority is result.proposal.repair_scope_authority is False
    assert result.proposal.execution_authorized is result.proposal.auto_apply is False
    assert result.proposal.apply_authority is False
    assert result.proposal.candidate is None and result.proposal.patch == ""
    assert result.first_remaining_blocker == "SCOPE_APPROVAL_NOT_IMPLEMENTED"
    assert "NEEDS_TRANSITION_DECISION" not in {
        item.certainty for item in result.proposal.required_capabilities}
    assert _transition_capability(result.proposal).certainty == "MUST_SUPPORT"
    assert result.structural_semantic_fixpoint is True
    assert result.post_refresh_recheck["status"] == "semantic_recheck_not_required"
    assert result.post_refresh_recheck["proposal_fingerprint"] == result.proposal.fingerprint
    assert args["historical_proposal"].to_json() == p0_json
    post = recheck_refreshed_scope_semantics(refreshed_proposal=result.proposal, **args)
    assert post.status == "semantic_recheck_not_required"
    assert post.scope_refresh_required is False
    assert post.effective_design_fingerprint == effective.fingerprint
    assert "SavingAccount" in {item.owner for item in result.proposal.new_logical_targets}
    assert any(item.name == "savingBalance" for item in result.proposal.new_logical_targets)
    assert any(item.code == "authentication_gated_savings_operation"
               for item in result.proposal.required_capabilities)
    assert any(item.code == "savings_interest_behavior"
               for item in result.proposal.required_capabilities)
    assert any(item.code == "base_balance_debit"
               for item in result.proposal.required_capabilities)
    assert any(item.category == "MAY_REQUIRE_EXISTING_API_CHANGE"
               and item.target == "BankAccount::successful_balance_debit_capability"
               for item in result.proposal.existing_targets)
    assert any(item.target == "SavingAccount" and item.decision == "source_layout"
               for item in result.proposal.deferred_decisions)
    assert not any("SavingAccount.java" in json for json in
                   (result.proposal.to_json(),))
    assert result.proposal.schema_version == "patch_scope_refresh_1_v1"
    assert result.proposal.scope_authority == "proposal_only"


def test_three_semantic_choices_have_distinct_bank_saving_requirements(tmp_path):
    results = {value: _refresh(_chain(tmp_path / value, value)[1])
               for value in TRANSITION_ANSWERS}
    for result in results.values():
        _assert_proposal_only(result)
    sub = _target(results["savings_only_on_subclass"].proposal)
    compatible = _target(results["preserve_base_compatibility"].proposal)
    specialized = _target(results["subclass_specialization"].proposal)
    assert sub.category == "MAY_REQUIRE_EXISTING_API_CHANGE"
    assert sub.reason == "base_savings_behavior_must_leave_intended_api"
    assert compatible.category == "DEFERRED_IMPLEMENTATION_TARGET"
    assert compatible.reason == "legacy_base_savings_behavior_is_semantically_preserved"
    assert specialized.category == "DEFERRED_IMPLEMENTATION_TARGET"
    assert specialized.reason == "base_savings_contract_supports_subclass_specialization"
    assert len({(x.category, x.reason) for x in (sub, compatible, specialized)}) == 3
    assert _transition_capability(results["preserve_base_compatibility"].proposal).requirement.find(
        "semantically required") >= 0
    assert not any(x.decision == "base_savings_retirement_or_compatibility_migration"
                   for x in results["preserve_base_compatibility"].proposal.deferred_decisions)
    assert not any(x.category == "MAY_REQUIRE_EXISTING_API_CHANGE" and "saving" in x.target.lower()
                   for x in results["subclass_specialization"].proposal.existing_targets)
    for result in results.values():
        diff = result.semantic_diff
        assert diff["deferred_decisions_resolved"]
        assert diff["target_certainty_changed"]
        assert "BankAccount::saving" in {item["target"]
            for item in diff["target_classification_or_reason_changes"]}


def test_refresh_suppresses_base_debit_api_change_when_exact_method_is_sufficient(tmp_path):
    source = MEASURED_BANK.replace(
        "if (amount <= balance) { balance -= amount; }", "balance -= amount;")
    _, args, *_ = _chain(tmp_path, source=source)
    result = _refresh(args)
    _assert_proposal_only(result)
    assert not any(item.target == "BankAccount::successful_balance_debit_capability"
                   for item in result.proposal.existing_targets)


@pytest.mark.parametrize("answer", ["Make it work somehow.", "Use protected fields and change the method signature."])
def test_unresolved_or_unknown_transition_never_refreshes(tmp_path, answer):
    _, args, continuation, _, receipt = _chain(tmp_path, answer=answer)
    assert continuation.status == "answer_projection_bounded"
    assert receipt.status == "answer_projection_bounded"
    result = _refresh(args)
    assert result.status == "semantic_transition_unresolved"
    assert result.proposal is None and not result.structural_semantic_fixpoint


def test_conflicting_transition_never_refreshes(tmp_path):
    _, args, continuation, _, receipt = _chain(
        tmp_path, answer="SavingAccount should not extend BankAccount.")
    assert continuation.status == "continuation_conflict"
    assert receipt.status == "continuation_conflict"
    result = _refresh(args)
    assert result.status == "semantic_transition_unresolved" and result.proposal is None


def test_stale_source_rejects_refresh_with_reacquisition(tmp_path):
    _, args, *_ = _chain(tmp_path)
    result = _refresh(args, current_source=args["current_source"] + b"\n// changed")
    assert result.status == "reacquisition_required" and result.proposal is None


def test_forged_historical_proposal_transition_and_wrong_parent_are_rejected(tmp_path):
    _, args, continuation, effective, receipt = _chain(tmp_path)
    p0 = args["historical_proposal"]
    forged_p0 = replace(p0, reasons=("forged",))
    assert _refresh(args, historical_proposal=forged_p0).status == "invalid_proposal"
    altered_transition = replace(continuation, answer_fingerprint="a" * 64,
                                 answer_record_fingerprint="b" * 64)
    altered_effective = compose_scope_transition_design(
        compose_effective_for_test(args), altered_transition)
    assert _refresh({**args, "scope_transition_effective_design": altered_effective}).status == "invalid_proposal"
    assert _refresh({**args, "validated_recheck_receipt": replace(
        receipt, reasons=("forged receipt",))}).status == "invalid_proposal"
    forged_continuation = replace(continuation, proposal_fingerprint="a" * 64)
    forged_effective = compose_scope_transition_design(
        compose_effective_for_test(args), forged_continuation)
    wrong_parent_args = {**args, "transition_continuation": forged_continuation,
                         "scope_transition_effective_design": forged_effective}
    assert _refresh(wrong_parent_args).status == "invalid_proposal"
    altered_commitment = replace(continuation.typed_answer_commitments[0], value="preserve_base_compatibility")
    forged_semantics = replace(continuation, typed_answer_commitments=(altered_commitment,))
    forged_design = compose_scope_transition_design(compose_effective_for_test(args), forged_semantics)
    assert _refresh({**args, "transition_continuation": forged_semantics,
                     "scope_transition_effective_design": forged_design}).status == "invalid_proposal"
    good = _refresh(args)
    assert _refresh({**args, "historical_proposal": good.proposal}).status == "invalid_proposal"


def compose_effective_for_test(args):
    from core.design_intent_continuation import compose_effective_design
    return compose_effective_design(args["original_design_intent"], args["continue1_continuation"])


def test_bank1_is_not_applicable(tmp_path):
    _, args, *_ = _chain(tmp_path)
    review_contract = replace(args["task_contract"],
        task=replace(args["task_contract"].task, type="review"))
    result = _refresh({**args, "task_contract": review_contract})
    assert result.status == "not_applicable" and result.proposal is None


def test_current_scope_fingerprint_is_bound_without_scope_mutation(tmp_path):
    _, args, *_ = _chain(tmp_path)
    scope = object()
    result = _refresh({**args, "current_scope": scope,
                       "expected_scope_fingerprint": scope_fingerprint(None)})
    assert result.status == "invalid_proposal"
    assert result.repair_scope_delta == result.authoring_scope_delta == 0


def test_refresh_performs_no_provider_io_file_io_or_repository_traversal(tmp_path):
    _, args, *_ = _chain(tmp_path)

    def forbidden(*_a, **_kw):
        raise AssertionError("refresh attempted provider, file I/O, traversal, or execution")

    forbidden_targets = ("socket.create_connection", "socket.socket.connect", "subprocess.run",
        "subprocess.Popen", "os.system", "os.walk", "os.scandir", "os.listdir",
        "pathlib.Path.open", "pathlib.Path.read_bytes", "pathlib.Path.read_text",
        "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open")
    with pytest.MonkeyPatch.context() as mp:
        for target in forbidden_targets:
            mp.setattr(target, forbidden)
        result = _refresh(args)
    _assert_proposal_only(result)


def test_refresh_performance_has_each_required_stage(tmp_path):
    _, args, *_ = _chain(tmp_path)
    timings = {}
    result = _refresh(args, timings=timings)
    _assert_proposal_only(result)
    assert set(timings) == {
        "parent_validation_seconds", "revised_semantic_validation_seconds",
        "scope_regeneration_seconds", "semantic_diff_seconds",
        "post_refresh_recheck_seconds", "total_seconds",
    }
    assert all(value >= 0 for value in timings.values())
