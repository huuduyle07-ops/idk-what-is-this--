"""OOP.INTENT.CONTINUE.1: answer evidence, immutable chains, semantic readiness."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import copy
import json
import os
import socket
import subprocess

import pytest

from core.design_intent_continuation import (
    compose_effective_design,
    continue_design_intent,
)
from core.input_understanding import understand_request
from core.oop_intent_detector import (
    AUTH_DIMENSIONS,
    SAVINGS_DIMENSIONS,
    detect_missing_future_design_contract,
)
from core.oop_intent_session import bind_human_answer, make_stored_future_design_gap
from core.repository_identity import derive_repository_id
from tests.test_oop_intent_detect2 import BANK, BANK2_TASK, _inputs
from tests.test_auth_web1 import web


AUTH_ANSWER = """For this exercise, let SavingAccount own a simple password in memory.
It does not need to persist across runs.
Verify it when a savings operation is requested."""
SAVINGS_ANSWER = """savingBalance should receive money transferred from the inherited balance,
and interest should apply only to savingBalance."""
COMPLETE_ANSWER = AUTH_ANSWER + "\n\n" + SAVINGS_ANSWER
MATERIAL_DIMENSIONS = AUTH_DIMENSIONS | SAVINGS_DIMENSIONS


def _bound(repo, answer=COMPLETE_ANSWER):
    (repo / "bank.java").write_bytes(BANK.encode("utf-8"))
    contract, design, context, raw = _inputs(repo)
    detected = detect_missing_future_design_contract(
        task_contract=contract, design_intent=design, current_context=context,
        current_source=raw, repository_id=derive_repository_id(repo))
    gap = make_stored_future_design_gap(
        detected, task_text=BANK2_TASK, repo_path=str(repo))
    return dict(task_contract=contract, base_design=design, stored_gap=gap,
                stored_answer=bind_human_answer(gap, answer).as_dict(),
                current_context=context, current_source=raw, repo_path=str(repo))


def _redetect(bound, continuation, **overrides):
    arguments = dict(
        task_contract=bound["task_contract"],
        design_intent=compose_effective_design(bound["base_design"], continuation),
        current_context=bound["current_context"], current_source=bound["current_source"],
        repository_id=derive_repository_id(bound["repo_path"]),
        stored_gap=bound["stored_gap"], stored_answer=bound["stored_answer"],
        repo_path=bound["repo_path"],
    )
    arguments.update(overrides)
    return detect_missing_future_design_contract(**arguments)


def _values(continuation):
    return {item.dimension: item.value for item in continuation.typed_answer_commitments}


def test_complete_bank2_answer_resolves_exact_material_contract_and_redetects_no_gap(tmp_path):
    bound = _bound(tmp_path)
    continuation = continue_design_intent(**bound)
    assert continuation.status == "clarification_projected"
    assert set(continuation.resolved_dimensions) == MATERIAL_DIMENSIONS
    assert not continuation.remaining_dimensions
    values = _values(continuation)
    assert values["credential_ownership"] == "SavingAccount"
    assert values["credential_persistence"] == "in_memory_only"
    assert values["verification_lifecycle"] == "operation_gated"
    assert values["credential_source"]
    assert values["credential_verification_mechanism"]
    assert values["savings_funding_semantics"] == "transfer_from_inherited_balance"
    assert values["savings_interest_semantics"] == "interest_applies_to_saving_balance"
    result = _redetect(bound, continuation)
    assert result.status == "no_gap" and result.gap is None
    dispositions = {item.dimension: item.disposition for item in result.assessments}
    assert dispositions["source_layout"] == "deferred_implementation"
    assert dispositions["subclass_creation_lifecycle"] == "deferred_implementation"
    assert result.author_calls == result.model_calls == result.repository_traversals == 0
    assert result.patch_candidate is None and result.patch == ""


@pytest.mark.parametrize(("answer", "resolved", "remaining"), [
    (AUTH_ANSWER, AUTH_DIMENSIONS, SAVINGS_DIMENSIONS),
    (SAVINGS_ANSWER, SAVINGS_DIMENSIONS, AUTH_DIMENSIONS),
])
def test_partial_answers_produce_one_narrower_gap_without_repeating_resolved_questions(
        tmp_path, answer, resolved, remaining):
    bound = _bound(tmp_path, answer)
    continuation = continue_design_intent(**bound)
    assert continuation.status == "clarification_projected"
    assert set(continuation.resolved_dimensions) == resolved
    assert set(continuation.remaining_dimensions) == remaining
    result = _redetect(bound, continuation)
    assert result.status == "clarification_required"
    assert len(result.possible_intent_gaps) == 1
    assert set(result.gap.subdimensions) == remaining
    question = result.gap.question.casefold()
    if remaining == SAVINGS_DIMENSIONS:
        assert "remaining savings behavior" in question
        assert "credential" not in question
    else:
        assert "remaining verification contract" in question
        assert "how savingbalance is funded" not in question


def test_persistent_answer_resolves_semantics_without_storage_or_hashing_choices(tmp_path):
    bound = _bound(tmp_path, "Credentials must persist across runs.")
    continuation = continue_design_intent(**bound)
    assert continuation.status == "clarification_projected"
    assert _values(continuation) == {"credential_persistence": "persists_across_runs"}
    result = _redetect(bound, continuation)
    assert result.status == "clarification_required"
    assert set(result.gap.subdimensions) == MATERIAL_DIMENSIONS - {"credential_persistence"}
    text = json.dumps(continuation.as_dict()).casefold() + result.to_json().casefold()
    assert all(word not in text for word in ("sqlite", "csv", "database", "bcrypt", "hash_algorithm"))


def test_gap_scoped_memory_pronoun_resolves_only_persistence(tmp_path):
    bound = _bound(tmp_path, "Keep it only in memory for this exercise.")
    continuation = continue_design_intent(**bound)
    assert _values(continuation) == {"credential_persistence": "in_memory_only"}
    assert set(continuation.remaining_dimensions) == MATERIAL_DIMENSIONS - {"credential_persistence"}


@pytest.mark.parametrize("answer", [
    "Make it nice and sensible.",
    "Use the special blue mechanism we discussed elsewhere.",
    "Maybe SavingAccount could own the password?",
])
def test_unknown_or_noncommittal_answer_fails_closed_without_claiming_resolution(tmp_path, answer):
    bound = _bound(tmp_path, answer)
    continuation = continue_design_intent(**bound)
    assert continuation.status == "answer_projection_bounded"
    assert not continuation.typed_answer_commitments
    assert not continuation.resolved_dimensions
    assert set(continuation.remaining_dimensions) == MATERIAL_DIMENSIONS
    result = _redetect(bound, continuation)
    assert result.status != "no_gap"


def test_every_answer_commitment_retains_exact_explicit_human_span_and_record_binding(tmp_path):
    bound = _bound(tmp_path)
    continuation = continue_design_intent(**bound)
    answer = bound["stored_answer"]
    assert continuation.answer_fingerprint == answer["answer_fingerprint"]
    assert continuation.parent_gap_id == bound["stored_gap"]["gap_id"]
    assert continuation.parent_design_fingerprint == bound["base_design"].fingerprint
    assert continuation.task_contract_fingerprint == bound["base_design"].task_contract_fingerprint
    assert continuation.repository_id == bound["stored_gap"]["repository_id"]
    assert continuation.source_fingerprint == bound["stored_gap"]["source_fingerprint"]
    for commitment in continuation.typed_answer_commitments:
        assert commitment.answer_fingerprint == answer["answer_fingerprint"]
        span = commitment.evidence
        assert span.provenance == "explicit_human"
        assert answer["text"][span.source_start:span.source_end] == span.source_text


def test_base_and_source_stay_immutable_and_effective_view_preserves_all_base_commitments(tmp_path):
    bound = _bound(tmp_path)
    base = bound["base_design"]
    before_base = base.as_dict()
    before_source = (tmp_path / "bank.java").read_bytes()
    before_context = bound["current_context"].as_dict()
    continuation = continue_design_intent(**bound)
    effective = compose_effective_design(base, continuation)
    assert base.as_dict() == before_base
    assert effective.fingerprint != base.fingerprint
    for name in ("relationships", "state_commitments", "behavior_gates", "explicit_absences"):
        assert getattr(effective, name) == getattr(base, name)
    assert bound["current_context"].as_dict() == before_context
    assert (tmp_path / "bank.java").read_bytes() == before_source
    assert not (tmp_path / "SavingAccount.java").exists()

    assert not (tmp_path / "sessions.json").exists()
    assert "SavingAccount.java" not in json.dumps(continuation.as_dict())
    with pytest.raises(FrozenInstanceError):
        continuation.status = "implemented"
    with pytest.raises(FrozenInstanceError):
        continuation.typed_answer_commitments[0].value = "rewritten"
    assert isinstance(continuation.typed_answer_commitments, tuple)
    detached = continuation.as_dict()
    detached["typed_answer_commitments"][0]["value"] = "rewritten"
    assert continuation.typed_answer_commitments[0].value != "rewritten"


def _waiting_session(web):
    from web.oop_intent_adapter import admit_future_design_control_wait
    from web.session_store import find_session
    (web.repo / "bank.java").write_bytes(BANK.encode())
    wait, _ = admit_future_design_control_wait(
        control={"patch_intent": {"file": "bank.java", "target_symbol": "BankAccount"}},
        repo_path=str(web.repo), task_text=BANK2_TASK)
    return find_session(wait["clarification_session_id"])


def _submit(web, session, text, **overrides):
    data = {"session_id": session["id"], "gap_id": session["oop_intent_gap"]["gap_id"],
            "repo_path": session["repo_path"], "answer": text, **overrides}
    with web.app.test_request_context("/oop_intent/answer", method="POST", data=data):
        return web.wa.answer_oop_intent()


@pytest.mark.parametrize(("answer", "dimensions"), [
    (COMPLETE_ANSWER, set()), (AUTH_ANSWER, SAVINGS_DIMENSIONS),
    (SAVINGS_ANSWER, AUTH_DIMENSIONS),
    ("Credentials must persist across runs.", MATERIAL_DIMENSIONS - {"credential_persistence"}),
])
def test_stored_session_answer_projects_once_and_stops_before_authoring(web, monkeypatch, answer, dimensions):
    from web import session_store
    session = _waiting_session(web)
    before = (web.repo / "bank.java").read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("semantic continuation must stop before scope/prompt/authoring")

    monkeypatch.setattr(web.wa, "build_control_prompt", forbidden)
    monkeypatch.setattr(web.wa, "run_gemini_request", forbidden)
    result = _submit(web, session, answer)
    assert result["status"] == "clarification_projected", result
    assert set(result["design_intent_continuation"]["remaining_dimensions"]) == dimensions
    assert result["oop_intent_detection"]["status"] == ("clarification_required" if dimensions else "no_gap")
    stored = session_store.find_session(session["id"])
    assert stored["status"] == "clarification_projected"
    assert stored["events"] == ["waiting_for_clarification", "clarification_supplied",
                                "clarification_supplied_pending_projection", "clarification_projected"]
    assert stored["oop_intent_gap"] == session["oop_intent_gap"]
    assert _submit(web, session, answer) == result
    assert session_store.find_session(session["id"]) == stored
    assert len(session_store.load_sessions()) == 1
    assert (web.repo / "bank.java").read_bytes() == before
    assert not (web.repo / "SavingAccount.java").exists()
    assert "repair_scope" not in stored["control"]
    assert result["patch_candidate"] is None and result["patch"] == ""
    assert result["model_calls"] == result["repository_traversals"] == result["patch_author_calls"] == 0
    assert all(value >= 0 for value in result["continuation_timings"].values())
    assert set(result["continuation_timings"]) == {
        "answer_extraction_seconds", "continuation_construction_seconds",
        "effective_projection_seconds", "detection_reentry_seconds", "total_seconds"}
    conflict = _submit(web, session, "A different answer.")
    assert conflict[1] == 409 and conflict[0]["code"] == "clarification_conflict"
    assert session_store.find_session(session["id"]) == stored


@pytest.mark.parametrize("after_projection", [False, True])
def test_live_source_staleness_requires_reacquisition_without_overwriting_revision(web, after_projection):
    from web import session_store
    session = _waiting_session(web)
    if after_projection:
        assert _submit(web, session, COMPLETE_ANSWER)["status"] == "clarification_projected"
    previous = session_store.find_session(session["id"])
    (web.repo / "bank.java").write_bytes(BANK.encode() + b"\n// source changed")
    response = _submit(web, session, COMPLETE_ANSWER)
    result = response[0] if isinstance(response, tuple) else response
    assert result["status"] == "reacquisition_required"
    if after_projection:
        assert session_store.find_session(session["id"]) == previous


@pytest.mark.parametrize("field", ["design_intent_continuation", "effective_design_intent", "oop_intent_detection", "write_authority"])
def test_live_retry_rejects_forged_stored_results(web, field):
    from web import session_store
    session = _waiting_session(web)
    assert _submit(web, session, COMPLETE_ANSWER)["status"] == "clarification_projected"
    sessions = session_store.load_sessions()
    payload = sessions[0]["result"]
    if field == "write_authority":
        payload[field] = True
    elif field == "design_intent_continuation":
        payload[field]["resolved_dimensions"] = []
    else:
        payload[field]["status"] = "forged"
    session_store.save_sessions(sessions)
    result = _submit(web, session, COMPLETE_ANSWER)
    assert result["status"] == "rejected"
    assert result["write_authority"] is False


def test_live_wrong_gap_and_resume_of_already_stored_pending_answer(web):
    from web import session_store
    from web.oop_intent_continuation import project_stored_oop_answer
    session = _waiting_session(web)
    wrong = _submit(web, session, COMPLETE_ANSWER, gap_id="0" * 64)
    assert wrong[1] == 409 and wrong[0]["code"] == "wrong_gap"
    answer = bind_human_answer(session["oop_intent_gap"], COMPLETE_ANSWER).as_dict()
    session_store.update_oop_intent_wait(session["id"],
        status="clarification_supplied_pending_projection", answer=answer)
    result = project_stored_oop_answer(session["id"])
    assert result["status"] == "clarification_projected"
    assert len(session_store.load_sessions()) == 1


def test_identical_answer_retry_is_idempotent_without_duplicate_evidence(tmp_path):
    bound = _bound(tmp_path)
    first = continue_design_intent(**bound)
    second = continue_design_intent(**bound)
    retried = continue_design_intent(**bound, previous=first)
    assert first.fingerprint == second.fingerprint == retried.fingerprint
    assert first.typed_answer_commitments == second.typed_answer_commitments == retried.typed_answer_commitments
    assert len(first.typed_answer_commitments) == len(MATERIAL_DIMENSIONS)
    assert compose_effective_design(bound["base_design"], first).fingerprint == (
        compose_effective_design(bound["base_design"], retried).fingerprint)


def test_different_answer_cannot_overwrite_existing_continuation(tmp_path):
    bound = _bound(tmp_path)
    first = continue_design_intent(**bound)
    bound["stored_answer"] = bind_human_answer(
        bound["stored_gap"], "Credentials must persist across runs.").as_dict()
    with pytest.raises(ValueError, match="conflict"):
        continue_design_intent(**bound, previous=first)


@pytest.mark.parametrize("answer", [
    "Actually put savingBalance on BankAccount.",
    "Do not use inheritance.",
    "Savings functionality must not require password verification.",
])
def test_base_commitment_reversal_is_a_conflict_without_superseding_base(tmp_path, answer):
    bound = _bound(tmp_path, answer)
    before = bound["base_design"].as_dict()
    continuation = continue_design_intent(**bound)
    assert continuation.status == "continuation_conflict"
    assert continuation.conflicts
    assert bound["base_design"].as_dict() == before
    assert _redetect(bound, continuation).status != "no_gap"


def test_contradictory_answer_commitments_fail_closed(tmp_path):
    bound = _bound(tmp_path, "Keep it only in memory for this exercise. Credentials must persist across runs.")
    continuation = continue_design_intent(**bound)
    assert continuation.status == "continuation_conflict"
    assert continuation.conflicts


@pytest.mark.parametrize("field", [
    "gap_id", "task_fingerprint", "repository_id", "source_fingerprint",
    "evidence_fingerprint", "answer_fingerprint",
])
def test_wrong_or_forged_answer_record_binding_is_rejected(tmp_path, field):
    bound = _bound(tmp_path)
    bound["stored_answer"] = {**bound["stored_answer"], field: "0" * 64}
    with pytest.raises(ValueError):
        continue_design_intent(**bound)


def test_answer_text_tampering_without_new_fingerprint_is_rejected(tmp_path):
    bound = _bound(tmp_path)
    bound["stored_answer"]["text"] = "Credentials must persist across runs."
    with pytest.raises(ValueError):
        continue_design_intent(**bound)


def test_wrong_gap_wrong_task_and_wrong_repository_are_rejected(tmp_path):
    bound = _bound(tmp_path)
    altered_gap = copy.deepcopy(bound["stored_gap"])
    altered_gap["gap_id"] = "0" * 64
    with pytest.raises(ValueError):
        continue_design_intent(**{**bound, "stored_gap": altered_gap})
    with pytest.raises(ValueError):
        continue_design_intent(**{**bound, "task_contract": understand_request("Review BankAccount.")})
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "bank.java").write_bytes(bound["current_source"])
    with pytest.raises(ValueError):
        continue_design_intent(**{**bound, "repo_path": str(elsewhere)})


def test_altered_base_projection_is_recomputed_and_rejected(tmp_path):
    bound = _bound(tmp_path)
    forged_base = replace(bound["base_design"], behavior_gates=())
    with pytest.raises(ValueError):
        continue_design_intent(**{**bound, "base_design": forged_base})


def test_stale_exact_source_requires_reacquisition(tmp_path):
    bound = _bound(tmp_path)
    with pytest.raises(ValueError, match="reacquisition|stale"):
        continue_design_intent(**{**bound, "current_source": bound["current_source"] + b"\n// changed"})
    (tmp_path / "bank.java").write_bytes(bound["current_source"] + b"\n// changed")
    # The pure core validates freshly supplied bytes. The session adapter owns
    # exact on-disk reacquisition (covered separately through its live route).
    with pytest.raises(ValueError, match="reacquisition|stale"):
        continue_design_intent(**{**bound, "current_source": (tmp_path / "bank.java").read_bytes()})


def test_detector_reentry_requires_the_exact_stored_human_answer(tmp_path):
    bound = _bound(tmp_path)
    continuation = continue_design_intent(**bound)
    different = bind_human_answer(bound["stored_gap"], "Credentials must persist across runs.").as_dict()
    result = _redetect(bound, continuation, stored_answer=different)
    assert result.status != "no_gap" and result.gap is None
    result = _redetect(bound, continuation, stored_answer=None)
    assert result.status != "no_gap" and result.gap is None


def test_forged_typed_commitment_cannot_pass_deterministic_revalidation(tmp_path):
    bound = _bound(tmp_path)
    continuation = continue_design_intent(**bound)
    commitments = tuple(
        replace(item, value="BankAccount") if item.dimension == "credential_ownership" else item
        for item in continuation.typed_answer_commitments)
    forged = replace(continuation, typed_answer_commitments=commitments)
    result = _redetect(bound, forged)
    assert result.status != "no_gap" and result.gap is None


def test_continuation_has_no_write_execution_apply_or_scope_authority(tmp_path):
    bound = _bound(tmp_path)
    continuation = continue_design_intent(**bound)
    effective = compose_effective_design(bound["base_design"], continuation)
    result = _redetect(bound, continuation)
    for artifact in (continuation, effective, result):
        assert artifact.authority == "read_only"
        for field in ("write_authority", "execution_authorized", "auto_apply", "repair_scope_authority"):
            assert getattr(artifact, field) is False
    for field in ("write_authority", "execution_authorized", "auto_apply", "repair_scope_authority"):
        with pytest.raises((ValueError, TypeError)):
            replace(continuation, **{field: True})


def test_continuation_has_no_provider_execution_traversal_or_source_mutation(tmp_path, monkeypatch):
    from core.semantic_waiter_adapter import SemanticWaiterModelAdapter

    bound = _bound(tmp_path)
    before = (tmp_path / "bank.java").read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("answer continuation cannot author, execute, traverse, or call a model")

    with monkeypatch.context() as guard:
        guard.setattr(os, "walk", forbidden)
        guard.setattr(os, "scandir", forbidden)
        guard.setattr(socket, "create_connection", forbidden)
        guard.setattr(subprocess, "run", forbidden)
        guard.setattr(SemanticWaiterModelAdapter, "_complete", forbidden)
        continuation = continue_design_intent(**bound)
        result = _redetect(bound, continuation)
    assert result.status == "no_gap"
    assert result.author_calls == result.model_calls == result.repository_traversals == 0
    assert result.patch_candidate is None and result.patch == ""
    assert (tmp_path / "bank.java").read_bytes() == before
    assert not (tmp_path / "SavingAccount.java").exists()


@pytest.mark.parametrize(("answer", "dimension", "value"), [
    ("SavingAccount stores/checks a password in memory.", "credential_verification_mechanism", "semantic_password_check"),
    ("Let BankAccount own a simple password in memory.", "credential_ownership", "BankAccount"),
    ("Let user/account identity own a simple password in memory.", "credential_ownership", "user/account identity"),
    ("Let application/session own a simple password in memory.", "credential_ownership", "application/session"),
    ("Credential owner: TreasuryService.", "credential_ownership", "explicit_other:TreasuryService"),
    ("Verify the password on creation.", "verification_lifecycle", "creation_gated"),
    ("Verify it at both creation and each savings operation.", "verification_lifecycle", "both"),
    ("savingBalance should be independently funded.", "savings_funding_semantics", "independently_funded"),
    ("Do not apply interest to savingBalance.", "savings_interest_semantics", "no_interest_behavior"),
    ("Credentials must persist across runs. Don't worry about hashing; this is only a practice exercise.",
     "exercise_hashing_constraint", "hashing_out_of_scope_for_this_exercise"),
])
def test_supported_semantic_alternatives_remain_explicit_and_task_bound(tmp_path, answer, dimension, value):
    bound = _bound(tmp_path, answer)
    continuation = continue_design_intent(**bound)
    assert continuation.status == "clarification_projected"
    assert _values(continuation)[dimension] == value
    assert _redetect(bound, continuation).status == "clarification_required"
    assert "field_visibility" not in _values(continuation)
    assert "constructor_signature" not in _values(continuation)
    assert "storage_technology" not in _values(continuation)


@pytest.mark.parametrize("answer", [
    "Do not use an in-memory password on SavingAccount.",
    "If the teacher agrees, let SavingAccount own a simple password in memory.",
    "Interest applies only to savingBalance unless balance is negative.",
    "Transfer from savingBalance into inherited balance.",
    "Use SQLite and bcrypt.",
    "The password might persist across runs.",
])
def test_unsupported_qualifications_negations_and_technology_cannot_resolve_semantics(tmp_path, answer):
    bound = _bound(tmp_path, answer)
    continuation = continue_design_intent(**bound)
    assert continuation.status == "answer_projection_bounded"
    assert continuation.not_resolved_by_continuation
    assert not continuation.resolved_dimensions
    assert _redetect(bound, continuation).status == "projection_bounded"


def test_unclassified_clause_on_complete_answer_still_blocks_readiness(tmp_path):
    bound = _bound(tmp_path, COMPLETE_ANSWER + " But there is another condition we haven't discussed.")
    continuation = continue_design_intent(**bound)
    assert continuation.status == "answer_projection_bounded"
    assert _redetect(bound, continuation).status == "projection_bounded"


def test_answer_extracts_only_dimensions_in_the_active_gap(tmp_path):
    from core.clarification_answer_evidence import extract_clarification_answer
    bound = _bound(tmp_path, AUTH_ANSWER)
    answer = bind_human_answer(bound["stored_gap"], AUTH_ANSWER)
    evidence = extract_clarification_answer(answer, tuple(SAVINGS_DIMENSIONS), bound["base_design"])
    assert not evidence.commitments
    assert evidence.not_resolved_by_continuation
