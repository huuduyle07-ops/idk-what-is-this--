"""PATCH.SCOPE.RECHECK.1: synthetic transitions reuse the frozen OOP lifecycle.

The complete BANK.2 design answer is the frozen synthetic CONTINUE.1 fixture.
All transition answers here are synthetic. No real waiting answer is read.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.oop_intent_session import bind_human_answer, validate_stored_gap
from core.oop_semantic_review import OOPIntentGap
from core.scope_semantic_recheck import (
    compose_scope_transition_design, continue_scope_transition,
    make_stored_scope_transition_gap, recheck_scope_semantics,
)
from core.structural_scope_expansion import propose_structural_scope_expansion
from scripts.replay_patch_scope_expand1 import fixture_inputs
from tests.test_auth_web1 import web


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
SAVING_METHOD = """  public void saving(double interest, double year) {
    balance += balance * interest * year;
  }
"""
MAINAPP = """class MainApp {
  public static void main(String[] args) { System.out.println("untouched"); }
}"""
TRANSITION_ANSWERS = {
    "savings_only_on_subclass": (
        "Savings functionality should only belong to SavingAccount. "
        "BankAccount should no longer have savings behavior in the intended model."),
    "preserve_base_compatibility": (
        "Keep BankAccount's current saving behavior for compatibility, "
        "and SavingAccount should have separate savingBalance behavior."),
    "subclass_specialization": (
        "Keep a common savings operation concept, but SavingAccount should "
        "specialize it to use savingBalance."),
}


def _inputs(root, *, source=MEASURED_BANK):
    return fixture_inputs(repository_root=root, source=source)


def _arguments(inputs):
    return dict(task_contract=inputs["task_contract"],
                design_intent=inputs["design_intent"],
                semantic_detection=inputs["detection"],
                current_context=inputs["current_context"],
                current_source=inputs["current_source"],
                repository_id=inputs["repository_id"])


def _proposal(inputs):
    result = propose_structural_scope_expansion(**_arguments(inputs))
    assert result.status == "expansion_required"
    assert result.proposal is not None
    return result.proposal


def _without_saving():
    assert SAVING_METHOD in MEASURED_BANK
    return MEASURED_BANK.replace(SAVING_METHOD, "")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _recheck_arguments(inputs, proposal=None):
    return {**_arguments(inputs), "proposal": proposal or _proposal(inputs),
            "repo_path": inputs["repo_path"],
            "stored_gap": inputs["stored_gap"], "stored_answer": inputs["stored_answer"]}


def _recheck(inputs, **overrides):
    return recheck_scope_semantics(**{**_recheck_arguments(inputs), **overrides})


def _stored_gap(inputs, result=None):
    result = _recheck(inputs) if result is None else result
    gap = make_stored_scope_transition_gap(
        result, task_contract=inputs["task_contract"],
        current_context=inputs["current_context"], repository_id=inputs["repository_id"])
    assert gap is not None
    return gap


def _continue(inputs, text, *, previous=None, **overrides):
    gap = _stored_gap(inputs)
    answer = bind_human_answer(gap, text).as_dict()
    arguments = {**_recheck_arguments(inputs), "stored_transition_gap": gap,
                 "stored_transition_answer": answer, "previous": previous, **overrides}
    return continue_scope_transition(**arguments), gap, answer


def _assert_no_authority(result):
    for field in ("write_authority", "execution_authorized", "auto_apply", "repair_scope_authority"):
        assert getattr(result, field) is False
    assert result.scope_authority == "proposal_only"
    if hasattr(result, "candidate"):
        assert result.candidate is None
        assert result.patch == ""
    if hasattr(result, "author_calls"):
        assert result.author_calls == result.model_calls == result.repository_traversals == 0


def test_bank2_no_gap_scope_proposal_discovers_exactly_one_new_oop_transition_gap(tmp_path):
    inputs = _inputs(tmp_path)
    proposal = _proposal(inputs)
    assert inputs["detection"].status == "no_gap"
    result = _recheck(inputs, proposal=proposal)
    assert result.status == "clarification_required"
    assert isinstance(result.gap, OOPIntentGap)
    assert result.possible_intent_gaps == (result.gap,)
    assert result.gap.dimension == "existing_savings_transition"
    assert result.gap.owner == "human"
    assert result.scope_refresh_required is False
    question = result.gap.question.casefold()
    assert "bankaccount" in question and "saving" in question and "balance" in question
    assert "savingaccount" in question and "future" in question
    assert all(word not in question for word in ("constructor", "filename", "visibility", "password"))
    effects = {alternative.effect for alternative in result.gap.alternatives}
    assert set(TRANSITION_ANSWERS) <= effects
    assert len(effects) == 4
    _assert_no_authority(result)


def test_question_binds_proposal_design_exact_declaration_source_task_and_repository(tmp_path):
    inputs = _inputs(tmp_path)
    proposal = _proposal(inputs)
    result = _recheck(inputs, proposal=proposal)
    gap = _stored_gap(inputs, result)
    target = next(row for row in proposal.existing_targets if row.target == "BankAccount::saving")
    encoded = _json({"result": result.as_dict(), "gap": gap})
    for value in (proposal.fingerprint, inputs["design_intent"].fingerprint,
                  target.declaration_fingerprint, inputs["current_context"].source_fingerprint,
                  proposal.task_contract_fingerprint, inputs["repository_id"]):
        assert value in encoded
    assert gap["gap_kind"] == "oop_intent"
    assert gap["dimension"] == "existing_savings_transition"
    assert "HumanEvidenceGap" not in encoded and "ScopeClarificationGap" not in encoded
    validated = validate_stored_gap(
        gap, task_text=inputs["task_contract"].raw_request.text, repo_path=inputs["repo_path"])
    assert validated == gap
    assert "BankAccount" in _json(gap["current_facts"])
    assert "SavingAccount" in _json(gap["interpretations"])


@pytest.mark.parametrize("value", tuple(TRANSITION_ANSWERS))
def test_synthetic_answer_extends_immutable_chain_and_resolves_transition_without_edit_authority(tmp_path, value):
    inputs = _inputs(tmp_path)
    base_before = inputs["base_design"].as_dict()
    parent_before = inputs["continuation"].as_dict()
    effective_before = inputs["design_intent"].as_dict()
    proposal = _proposal(inputs)
    continuation, gap, answer = _continue(inputs, TRANSITION_ANSWERS[value])
    assert continuation.status == "clarification_projected"
    assert continuation.resolved_dimensions == ("existing_savings_transition",)
    assert continuation.remaining_dimensions == ()
    commitments = {item.dimension: item.value for item in continuation.typed_answer_commitments}
    assert commitments == {"existing_savings_transition": value}
    future = compose_scope_transition_design(inputs["design_intent"], continuation)
    assert future.fingerprint != inputs["design_intent"].fingerprint
    assert inputs["design_intent"].fingerprint in _json(future.as_dict())
    assert inputs["continuation"].fingerprint in _json(continuation.as_dict())
    result = _recheck(inputs, proposal=proposal, transition_continuation=continuation,
                      stored_transition_gap=gap, stored_transition_answer=answer)
    assert result.status == "no_gap"
    assert result.gap is None and result.possible_intent_gaps == ()
    assert result.scope_refresh_required is True
    assert inputs["base_design"].as_dict() == base_before
    assert inputs["continuation"].as_dict() == parent_before
    assert inputs["design_intent"].as_dict() == effective_before
    assert inputs["current_source"] == MEASURED_BANK.encode("utf-8")
    assert all(term not in _json(continuation.as_dict()) for term in
               ("@Override", "abstract void", "SavingAccount.java", "delete method"))
    for artifact in (continuation, future, result):
        _assert_no_authority(artifact)


@pytest.mark.parametrize("answer", [
    "Make it work somehow.",
    "Use protected fields and change the method signature.",
    "Maybe retain savings if the teacher says so.",
    TRANSITION_ANSWERS["savings_only_on_subclass"] + " Only if balance is negative.",
])
def test_unknown_conditional_or_implementation_answer_remains_unresolved(tmp_path, answer):
    inputs = _inputs(tmp_path)
    continuation, gap, record = _continue(inputs, answer)
    assert continuation.status == "answer_projection_bounded"
    assert not continuation.resolved_dimensions
    assert continuation.remaining_dimensions == ("existing_savings_transition",)
    assert not continuation.typed_answer_commitments
    result = _recheck(inputs, transition_continuation=continuation,
                      stored_transition_gap=gap, stored_transition_answer=record)
    assert result.status != "no_gap"
    assert result.scope_refresh_required is False
    _assert_no_authority(result)


@pytest.mark.parametrize("answer", [
    "Actually savingBalance should be on BankAccount.",
    "SavingAccount should not extend BankAccount.",
    "Interest should apply to inherited balance rather than savingBalance.",
])
def test_answer_conflicting_with_established_design_is_rejected_without_rewrite(tmp_path, answer):
    inputs = _inputs(tmp_path)
    before = inputs["design_intent"].as_dict()
    continuation, gap, record = _continue(inputs, answer)
    assert continuation.status == "continuation_conflict"
    assert not continuation.resolved_dimensions and not continuation.typed_answer_commitments
    result = _recheck(inputs, transition_continuation=continuation,
                      stored_transition_gap=gap, stored_transition_answer=record)
    assert result.status != "no_gap" and result.scope_refresh_required is False
    assert inputs["design_intent"].as_dict() == before


def test_identical_transition_answer_retry_is_idempotent_and_different_answer_fails_closed(tmp_path):
    inputs = _inputs(tmp_path)
    first, gap, answer = _continue(inputs, TRANSITION_ANSWERS["savings_only_on_subclass"])
    same, same_gap, same_answer = _continue(
        inputs, TRANSITION_ANSWERS["savings_only_on_subclass"], previous=first)
    assert same.fingerprint == first.fingerprint and same.as_dict() == first.as_dict()
    assert same_gap == gap and same_answer == answer
    with pytest.raises(ValueError):
        _continue(inputs, TRANSITION_ANSWERS["preserve_base_compatibility"], previous=first)


@pytest.mark.parametrize("source", [None, b"", MEASURED_BANK.encode("utf-8") + b"\n// changed"])
def test_missing_or_stale_current_source_requires_reacquisition_without_question(tmp_path, source):
    result = _recheck(_inputs(tmp_path), current_source=source)
    assert result.status == "reacquisition_required"
    assert result.gap is None and not result.possible_intent_gaps
    _assert_no_authority(result)


def test_stale_declaration_reprojection_cannot_reuse_old_proposal(tmp_path):
    original = _inputs(tmp_path)
    fresh = _inputs(tmp_path, source=MEASURED_BANK.replace("double year", "double years").replace("* year;", "* years;"))
    result = _recheck(fresh, proposal=_proposal(original))
    assert result.status in {"reacquisition_required", "invalid_proposal"}
    assert result.gap is None


@pytest.mark.parametrize("field", ["repository", "design", "source_context", "detection", "proposal"])
def test_forged_or_rebound_inputs_never_create_question_authority(tmp_path, field):
    inputs = _inputs(tmp_path)
    proposal = _proposal(inputs)
    overrides = {}
    if field == "repository":
        overrides["repository_id"] = "other-repository"
    elif field == "design":
        overrides["design_intent"] = _inputs(tmp_path, source=_without_saving())["design_intent"]
    elif field == "source_context":
        overrides["current_context"] = replace(inputs["current_context"], methods=tuple(
            replace(method, return_type="boolean") if method.name == "saving" else method
            for method in inputs["current_context"].methods))
    elif field == "detection":
        overrides["semantic_detection"] = replace(inputs["detection"], design_fingerprint="0" * 64)
    else:
        deferred = tuple(replace(item, alternatives=("delete", "preserve"))
                         if item.decision == "existing_savings_transition" else item
                         for item in proposal.deferred_decisions)
        overrides["proposal"] = replace(proposal, deferred_decisions=deferred)
    result = _recheck(inputs, **overrides)
    assert result.status == "invalid_proposal"
    assert result.gap is None and not result.possible_intent_gaps
    _assert_no_authority(result)


def test_no_transition_proposal_with_layout_constructor_visibility_and_api_details_has_no_gap(tmp_path):
    inputs = _inputs(tmp_path, source=_without_saving())
    proposal = _proposal(inputs)
    decisions = {item.decision for item in proposal.deferred_decisions}
    assert any("layout" in item for item in decisions)
    assert any("constructor" in item for item in decisions)
    assert any("visibility" in item for item in decisions)
    assert any("API_signature" in item for item in decisions)
    assert not any(item.semantic_recheck_if_behavior_changes for item in proposal.deferred_decisions)
    assert not any(item.certainty == "NEEDS_TRANSITION_DECISION" for item in proposal.required_capabilities)
    result = _recheck(inputs, proposal=proposal)
    assert result.status == "semantic_recheck_not_required"
    assert result.gap is None and not result.possible_intent_gaps
    assert result.scope_refresh_required is False
    _assert_no_authority(result)


@pytest.mark.parametrize("constructor", ["BankAccount(String accountHolder, double balance)",
    "BankAccount(double balance, String accountHolder)",
    "private BankAccount(String accountHolder, double balance)"])
def test_constructor_parameter_order_and_access_detail_do_not_create_material_gap(tmp_path, constructor):
    source = _without_saving().replace("BankAccount(String accountHolder, double balance)", constructor)
    inputs = _inputs(tmp_path, source=source)
    result = _recheck(inputs)
    assert result.status == "semantic_recheck_not_required" and result.gap is None


@pytest.mark.parametrize("withdraw", [
    "public void withdraw(double amount) { balance -= amount; }",
    "public boolean withdraw(double amount) { if (amount <= balance) { balance -= amount; return true; } return false; }",
    "protected boolean debit(double amount) { if (amount <= balance) { balance -= amount; return true; } return false; }",
])
def test_debit_implementation_variants_do_not_create_human_semantic_gap(tmp_path, withdraw):
    source = _without_saving().replace(
        "public void withdraw(double amount) {\n    if (amount <= balance) { balance -= amount; }\n  }", withdraw)
    result = _recheck(_inputs(tmp_path, source=source))
    assert result.status == "semantic_recheck_not_required" and result.gap is None


def test_semantic_answer_invalidates_old_proposal_as_current_design_authority(tmp_path):
    inputs = _inputs(tmp_path)
    proposal = _proposal(inputs)
    continuation, gap, answer = _continue(inputs, TRANSITION_ANSWERS["savings_only_on_subclass"])
    effective = compose_scope_transition_design(inputs["design_intent"], continuation)
    current = _recheck(inputs, proposal=proposal, transition_continuation=continuation,
                       stored_transition_gap=gap, stored_transition_answer=answer)
    assert current.status == "no_gap" and current.scope_refresh_required is True
    # A resolved lineage can use its old proposal as discovery provenance only.
    # It cannot rebind the old proposal as current scope authority for new meaning.
    changed = _recheck(inputs, proposal=proposal, design_intent=effective)
    assert changed.status == "invalid_proposal" and changed.gap is None


def test_forged_stored_gap_answer_or_continuation_is_rejected(tmp_path):
    inputs = _inputs(tmp_path)
    continuation, gap, answer = _continue(inputs, TRANSITION_ANSWERS["savings_only_on_subclass"])
    changed_gap = deepcopy(gap)
    changed_gap["question"] += " Changed by arbitrary prose."
    changed_answer = {**answer, "text": TRANSITION_ANSWERS["preserve_base_compatibility"]}
    forged_commitment = replace(continuation.typed_answer_commitments[0], value="preserve_base_compatibility")
    forged = replace(continuation, typed_answer_commitments=(forged_commitment,))
    for overrides in ({"stored_transition_gap": changed_gap}, {"stored_transition_answer": changed_answer},
                      {"transition_continuation": forged}):
        result = _recheck(inputs, **{"transition_continuation": continuation,
            "stored_transition_gap": gap, "stored_transition_answer": answer, **overrides})
        assert result.status == "invalid_proposal" and result.gap is None


def test_core_recheck_and_projection_perform_no_filesystem_traversal_model_author_or_execution(tmp_path):
    inputs = _inputs(tmp_path)
    arguments = _recheck_arguments(inputs)
    gap = _stored_gap(inputs)
    answer = bind_human_answer(gap, TRANSITION_ANSWERS["savings_only_on_subclass"]).as_dict()
    # Resolve modules before denying file access so imports are outside the phase.
    import core.control_engine
    import core.pipeline
    import core.semantic_waiter_adapter

    def forbidden(*args, **kwargs):
        raise AssertionError("scope semantic recheck crossed its immutable in-memory boundary")

    targets = (
        "core.semantic_waiter_adapter.SemanticWaiterModelAdapter._complete",
        "core.control_engine.build_control_prompt", "core.control_engine.authoring_context_for_control_result",
        "core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "socket.create_connection", "socket.socket.connect", "subprocess.run", "subprocess.Popen", "os.system",
        "os.walk", "os.scandir", "os.listdir", "pathlib.Path.open", "pathlib.Path.read_bytes",
        "pathlib.Path.read_text", "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open",
    )
    with ExitStack() as guards:
        for target in targets:
            guards.enter_context(patch(target, forbidden))
        first = recheck_scope_semantics(**arguments)
        continuation = continue_scope_transition(**arguments, stored_transition_gap=gap,
                                                   stored_transition_answer=answer)
        result = recheck_scope_semantics(**arguments, transition_continuation=continuation,
            stored_transition_gap=gap, stored_transition_answer=answer)
    assert first.status == "clarification_required" and result.status == "no_gap"
    _assert_no_authority(first)
    _assert_no_authority(result)


def test_recheck_measures_validation_classification_gap_projection_semantics_and_total(tmp_path):
    inputs = _inputs(tmp_path)
    timings = {}
    result = _recheck(inputs, timings=timings)
    assert result.status == "clarification_required"
    assert all(isinstance(value, (float, int)) and value >= 0 for value in timings.values())
    for token in ("proposal_validation", "transition_classification", "gap_construction", "semantic_recheck", "total"):
        assert any(token in field for field in timings)
    answer_timings = {}
    continuation, _, _ = _continue(inputs, TRANSITION_ANSWERS["savings_only_on_subclass"], timings=answer_timings)
    assert continuation.status == "clarification_projected"
    assert any("answer_projection" in field for field in answer_timings)
    assert not any("provider" in field for field in (*timings, *answer_timings))


def test_recheck_artifacts_have_fixed_immutable_authority(tmp_path):
    inputs = _inputs(tmp_path)
    result = _recheck(inputs)
    continuation, _, _ = _continue(inputs, TRANSITION_ANSWERS["savings_only_on_subclass"])
    effective = compose_scope_transition_design(inputs["design_intent"], continuation)
    for artifact in (result, continuation, effective):
        _assert_no_authority(artifact)
        with pytest.raises((FrozenInstanceError, AttributeError)):
            artifact.write_authority = True
        for field in ("write_authority", "execution_authorized", "auto_apply", "repair_scope_authority"):
            with pytest.raises((ValueError, TypeError)):
                replace(artifact, **{field: True})


def _web_wait(state, *, source=MEASURED_BANK):
    from web.scope_semantic_recheck import admit_scope_semantic_recheck_wait
    (state.repo / "bank.java").write_bytes(source.encode("utf-8"))
    (state.repo / "MainApp.java").write_bytes(MAINAPP.encode("utf-8"))
    inputs = _inputs(state.repo, source=source)
    result = admit_scope_semantic_recheck_wait(**_recheck_arguments(inputs))
    return result, inputs


def _web_answer(state, session, answer, *, gap_id=None):
    with state.app.test_request_context("/oop_intent/answer", method="POST", data={
        "session_id": session["id"], "gap_id": gap_id or session["oop_intent_gap"]["gap_id"],
        "repo_path": session["repo_path"], "answer": answer, "decline": "false",
    }):
        from web.app import answer_oop_intent
        return answer_oop_intent()


def _assert_safe_web_result(result):
    assert result["patch_candidate"] is result["candidate"] is None and result["patch"] == ""
    assert result["scope_authority"] == "proposal_only" and result["scope_delta"] == 0
    for key in ("write_authority", "execution_authorized", "auto_apply", "repair_scope_authority"):
        assert result[key] is False
    assert result["author_calls"] == result["model_calls"] == result["repository_traversals"] == 0


def test_transition_reuses_single_frozen_oop_ui_wait_and_explains_known_current_and_desired_facts(web):
    from web.session_store import find_session, load_sessions
    from web.session_presentation import project_session
    first, inputs = _web_wait(web)
    assert first["status"] == "waiting_for_clarification"
    session = find_session(first["clarification_session_id"])
    assert session["clarification_kind"] == "oop_intent" and session["task_mode"] == "patch"
    assert session["status"] == "waiting_for_clarification"
    assert session["clarification_answer"] is None
    assert session["events"] == ["waiting_for_clarification"]
    projected = project_session(session)
    assert projected["clarification"]["kind"] == "oop_intent"
    client = web.app.test_client()
    response = client.get("/session/" + session["id"])
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "BankAccount" in body and "SavingAccount" in body and "savingBalance" in body
    assert session["oop_intent_gap"]["question"] in body
    assert 'onclick="applyPatch()" hidden disabled' in body
    assert "BankAccount.java" not in session["oop_intent_gap"]["question"]
    repeated, _ = _web_wait(web)
    assert repeated["clarification_session_id"] == first["clarification_session_id"]
    assert len(load_sessions()) == 1
    assert find_session(session["id"])["clarification_answer"] is None
    assert web.calls == []
    _assert_safe_web_result(first)


@pytest.mark.parametrize("value", tuple(TRANSITION_ANSWERS))
def test_frozen_http_answer_path_projects_transition_and_stops_for_scope_refresh(web, value):
    from web.session_store import find_session, load_sessions
    waiting, inputs = _web_wait(web)
    session = find_session(waiting["clarification_session_id"])
    before = {name: (web.repo / name).read_bytes() for name in ("bank.java", "MainApp.java")}
    result = _web_answer(web, session, TRANSITION_ANSWERS[value])
    assert result["status"] == "clarification_projected"
    assert result["scope_semantic_recheck"]["status"] == "no_gap"
    assert result["scope_refresh_required"] is True
    assert result["first_remaining_blocker"] == "SCOPE_REFRESH_REQUIRED"
    commitments = result["scope_transition_continuation"]["typed_answer_commitments"]
    assert {item["dimension"]: item["value"] for item in commitments} == {"existing_savings_transition": value}
    assert not result["remaining_gap"]
    saved = find_session(session["id"])
    assert saved["clarification_answer"]["provenance"] == "human_provided_semantic_evidence"
    assert saved["events"] == ["waiting_for_clarification", "clarification_supplied", "clarification_projected"]
    assert len(load_sessions()) == 1
    assert _web_answer(web, session, TRANSITION_ANSWERS[value]) == result
    conflict = _web_answer(web, session, TRANSITION_ANSWERS[
        "preserve_base_compatibility" if value != "preserve_base_compatibility" else "savings_only_on_subclass"])
    assert conflict[1] == 409 and conflict[0]["code"] == "clarification_conflict"
    assert find_session(session["id"]) == saved
    for name, raw in before.items():
        assert (web.repo / name).read_bytes() == raw
    assert not (web.repo / "SavingAccount.java").exists()
    assert web.calls == []
    _assert_safe_web_result(result)


@pytest.mark.parametrize("answer,status", [
    ("I have not chosen the intended transition.", "answer_projection_bounded"),
    ("Actually savingBalance should be on BankAccount.", "continuation_conflict"),
])
def test_http_unknown_or_conflicting_answer_cannot_approve_scope_or_replace_design(web, answer, status):
    from web.session_store import find_session
    waiting, inputs = _web_wait(web)
    session = find_session(waiting["clarification_session_id"])
    parent = inputs["design_intent"].as_dict()
    result = _web_answer(web, session, answer)
    assert result["status"] == status
    assert result["scope_semantic_recheck"]["status"] != "no_gap"
    assert result["scope_refresh_required"] is False
    assert result["scope_transition_continuation"]["resolved_dimensions"] == []
    assert inputs["design_intent"].as_dict() == parent
    assert _web_answer(web, session, answer) == result
    _assert_safe_web_result(result)


def test_waiting_transition_source_freshness_precedes_answer_persistence(web):
    from web.session_store import find_session
    waiting, _ = _web_wait(web)
    session = find_session(waiting["clarification_session_id"])
    wrong = _web_answer(web, session, TRANSITION_ANSWERS["savings_only_on_subclass"], gap_id="0" * 64)
    assert wrong[1] == 409 and wrong[0]["code"] == "wrong_gap"
    (web.repo / "bank.java").write_bytes(MEASURED_BANK.encode("utf-8") + b"\n// changed")
    stale = _web_answer(web, session, TRANSITION_ANSWERS["savings_only_on_subclass"])
    assert stale[1] == 409 and stale[0]["status"] == "reacquisition_required"
    saved = find_session(session["id"])
    assert saved["clarification_answer"] is None
    assert saved["status"] == "waiting_for_clarification"
    assert "scope_transition_continuation" not in saved["result"]
    _assert_safe_web_result(stale[0])


def test_forged_proposal_admission_has_no_ui_session_or_question(web):
    from web.scope_semantic_recheck import admit_scope_semantic_recheck_wait
    from web.session_store import load_sessions
    (web.repo / "bank.java").write_bytes(MEASURED_BANK.encode("utf-8"))
    inputs = _inputs(web.repo)
    proposal = _proposal(inputs)
    forged = replace(proposal, reasons=(*proposal.reasons, "forged_scope_discovery"))
    result = admit_scope_semantic_recheck_wait(**{**_recheck_arguments(inputs), "proposal": forged})
    assert result["status"] == "invalid_proposal"
    assert load_sessions() == []
    assert "clarification_session_id" not in result
    _assert_safe_web_result(result)


def test_no_transition_admission_never_opens_session_for_implementation_details(web):
    from web.session_store import load_sessions
    result, _ = _web_wait(web, source=_without_saving())
    assert result["status"] == "semantic_recheck_not_required"
    assert load_sessions() == []
    _assert_safe_web_result(result)


def test_scope_transition_bridge_uses_typed_inputs_without_reparsing_task_or_traversing(web, monkeypatch):
    from web.session_store import find_session
    from web.scope_semantic_recheck import project_stored_scope_transition_answer
    import core.input_understanding
    from web import oop_intent_continuation as prior_continuation
    import os
    waiting, _ = _web_wait(web)
    session = find_session(waiting["clarification_session_id"])

    def forbidden(*args, **kwargs):
        raise AssertionError("scope transition must use its preserved typed input capsule")

    monkeypatch.setattr(core.input_understanding, "understand_request", forbidden)
    monkeypatch.setattr(prior_continuation, "understand_request", forbidden)
    monkeypatch.setattr(os, "walk", forbidden)
    monkeypatch.setattr(os, "scandir", forbidden)
    result = project_stored_scope_transition_answer(
        session["id"], answer_text=TRANSITION_ANSWERS["savings_only_on_subclass"],
        gap_id=session["oop_intent_gap"]["gap_id"])
    assert result["status"] == "clarification_projected"
    _assert_safe_web_result(result)


def test_bank1_review_gap_and_mainapp_remain_unchanged_by_scope_transition(web):
    from tests.test_ctx_oop_1c import review
    from web.session_store import find_session, create_oop_intent_wait
    from core.oop_intent_session import make_stored_gap
    waiting, inputs = _web_wait(web)
    bank1_task = "Review BankAccount logic; is saving correct?"
    before_review, _ = review(MEASURED_BANK, bank1_task)
    gap = make_stored_gap(before_review, task_text=bank1_task, repo_path=str(web.repo))
    bank1_id = create_oop_intent_wait(repo_path=str(web.repo), task_text=bank1_task, stored_gap=gap)
    bank1_before = find_session(bank1_id)
    mainapp_before = (web.repo / "MainApp.java").read_bytes()
    bank2 = find_session(waiting["clarification_session_id"])
    result = _web_answer(web, bank2, TRANSITION_ANSWERS["savings_only_on_subclass"])
    assert result["status"] == "clarification_projected"
    assert find_session(bank1_id) == bank1_before
    after_review, _ = review(MEASURED_BANK, bank1_task)
    assert after_review.status == before_review.status == "clarification_required"
    assert after_review.possible_intent_gaps == before_review.possible_intent_gaps
    assert (web.repo / "MainApp.java").read_bytes() == mainapp_before
    assert find_session(bank1_id)["clarification_answer"] is None


def _save_changed_session(session, change):
    from web.session_store import load_sessions, save_sessions, find_session
    sessions = load_sessions()
    for item in sessions:
        if item["id"] == session["id"]:
            change(item)
    save_sessions(sessions)
    return find_session(session["id"])


def test_projected_admission_retry_preserves_answer_revision_and_single_session(web):
    from web.session_store import find_session, load_sessions
    waiting, _ = _web_wait(web)
    session = find_session(waiting["clarification_session_id"])
    result = _web_answer(web, session, TRANSITION_ANSWERS["savings_only_on_subclass"])
    saved = find_session(session["id"])
    repeated, _ = _web_wait(web)
    assert repeated == result
    assert find_session(session["id"]) == saved
    assert len(load_sessions()) == 1


@pytest.mark.parametrize("tamper", ["authority", "candidate", "semantic_result", "question"])
def test_untrusted_waiting_question_or_authority_cannot_be_displayed_or_admitted(web, tamper):
    from web.session_store import find_session
    from web.scope_semantic_recheck import admit_scope_semantic_recheck_wait
    waiting, inputs = _web_wait(web)
    session = find_session(waiting["clarification_session_id"])

    def change(item):
        if tamper == "authority":
            item["result"]["write_authority"] = True
        elif tamper == "candidate":
            item["result"]["patch_candidate"] = {"file": "bank.java"}
        elif tamper == "semantic_result":
            item["result"]["scope_semantic_recheck"]["status"] = "no_gap"
        else:
            gap = item["oop_intent_gap"]
            gap["question"] = "Delete BankAccount.saving immediately?"
            gap["gap_id"] = sha256(_json({k: v for k, v in gap.items() if k != "gap_id"}).encode()).hexdigest()

    tampered = _save_changed_session(session, change)
    response = web.app.test_client().get("/session/" + session["id"])
    assert response.status_code == 422
    result = _web_answer(web, tampered, TRANSITION_ANSWERS["savings_only_on_subclass"])
    assert result[0]["status"] == "rejected"
    assert find_session(session["id"])["clarification_answer"] is None
    if tamper != "question":
        repeated = admit_scope_semantic_recheck_wait(**_recheck_arguments(inputs))
        assert repeated["status"] == "rejected"
        _assert_safe_web_result(repeated)
    assert web.calls == []


@pytest.mark.parametrize("metadata", ["unknown_schema", "remove_schema", "remove_schema_and_capsule"])
def test_transition_origin_metadata_tampering_cannot_fall_through_to_an_author(web, metadata):
    from web.session_store import find_session
    waiting, _ = _web_wait(web)
    session = find_session(waiting["clarification_session_id"])

    def change(item):
        gap = item["oop_intent_gap"]
        if metadata == "unknown_schema":
            gap["scope_recheck_schema"] = "untrusted_schema"
        else:
            del gap["scope_recheck_schema"]
        if metadata == "remove_schema_and_capsule":
            del item["result"]["scope_recheck_inputs"]
        gap["gap_id"] = sha256(_json({k: v for k, v in gap.items() if k != "gap_id"}).encode()).hexdigest()

    tampered = _save_changed_session(session, change)
    result = _web_answer(web, tampered, TRANSITION_ANSWERS["savings_only_on_subclass"])
    assert result[0]["status"] == "rejected" and result[0]["code"] == "wrong_gap"
    assert web.app.test_client().get("/session/" + session["id"]).status_code == 422
    assert find_session(session["id"])["clarification_answer"] is None
    assert web.calls == []


def test_projected_result_tampering_fails_closed_without_rewriting_revision(web):
    from web.session_store import find_session
    waiting, _ = _web_wait(web)
    session = find_session(waiting["clarification_session_id"])
    _web_answer(web, session, TRANSITION_ANSWERS["savings_only_on_subclass"])

    def change(item):
        item["result"]["scope_semantic_recheck"]["scope_refresh_required"] = False

    tampered = _save_changed_session(session, change)
    result = _web_answer(web, tampered, TRANSITION_ANSWERS["savings_only_on_subclass"])
    assert result[0]["code"] == "stored_projection_mismatch"
    assert find_session(session["id"]) == tampered


def test_stale_waiting_source_cannot_reuse_a_question_on_display(web):
    from web.session_store import find_session
    waiting, _ = _web_wait(web)
    session = find_session(waiting["clarification_session_id"])
    (web.repo / "bank.java").write_bytes(MEASURED_BANK.encode() + b"\n// changed")
    response = web.app.test_client().get("/session/" + session["id"])
    assert response.status_code == 422
    assert session["oop_intent_gap"]["question"] not in response.get_data(as_text=True)
    assert find_session(session["id"])["clarification_answer"] is None
