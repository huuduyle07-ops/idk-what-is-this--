"""Synthetic human actions only; never consume a real BANK.2 session."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from core.structural_scope_approval import (
    DECISIONS, TIMING_FIELDS, HumanScopeDecisionAction,
    prepare_structural_scope_review, decide_structural_scope_ceiling,
    validate_structural_scope_approval_receipt,
)
from tests.test_patch_scope_refresh1 import _chain, _refresh
from tests.test_patch_scope_recheck1 import MEASURED_BANK, TRANSITION_ANSWERS
from tests.test_auth_web1 import web, CSRF_META


def _inputs(root, transition="savings_only_on_subclass"):
    _, args, *_ = _chain(root, transition, source=MEASURED_BANK)
    result = _refresh(args)
    return dict(proposal=result.proposal, refresh_result=result, **args)


def _action(inputs, decision="approve_exact_scope_ceiling", note=""):
    review = prepare_structural_scope_review(**inputs)
    return HumanScopeDecisionAction(decision, review.proposal.fingerprint, review.fingerprint,
                                   "explicit_human", "synthetic_human_action", note)


def _safe(receipt):
    assert receipt.scope_authority == "proposal_only"
    assert receipt.repair_scope_delta == receipt.authoring_scope_delta == 0
    assert receipt.candidate is None and receipt.patch == ""
    assert receipt.author_calls == receipt.model_calls == receipt.repository_traversals == 0
    for name in ("write_authority", "execution_authorized", "auto_apply", "apply_authority", "repair_scope_authority"):
        assert getattr(receipt, name) is False


@pytest.mark.parametrize("transition", tuple(TRANSITION_ANSWERS))
def test_exact_p1_is_approved_without_admission(root_tmp_path, transition):
    inputs = _inputs(root_tmp_path, transition)
    p1, p0 = inputs["proposal"], inputs["historical_proposal"]
    before = p1.to_json(), p0.to_json(), inputs["current_source"]
    action = _action(inputs)
    receipt = decide_structural_scope_ceiling(**inputs, human_action=action)
    assert receipt.status == "approved_for_scope_admission" and receipt.eligible_for_admission is True
    assert receipt.approval_effect == "eligible_for_admission_only"
    assert receipt.proposal_fingerprint == p1.fingerprint
    assert receipt.parent_proposal_fingerprint == p0.fingerprint
    assert receipt.effective_design_fingerprint == inputs["scope_transition_effective_design"].fingerprint
    assert receipt.transition_continuation_fingerprint == inputs["transition_continuation"].fingerprint
    assert receipt.task_contract_fingerprint == p1.task_contract_fingerprint
    assert receipt.source_bindings == p1.source_bindings and receipt.repository_id == inputs["repository_id"]
    assert receipt.current_scope_fingerprint == p1.current_edit_scope.fingerprint
    assert receipt.approved_scope_ceiling.new_logical_targets == p1.new_logical_targets
    assert receipt.approved_scope_ceiling.existing_targets == p1.existing_targets
    assert receipt.approved_scope_ceiling.required_capabilities == p1.required_capabilities
    assert receipt.approved_scope_ceiling.deferred_decisions == p1.deferred_decisions
    assert receipt.approved_scope_ceiling.blast_radius == p1.blast_radius
    assert all(x.file is None for x in receipt.approved_scope_ceiling.new_logical_targets)
    logical = next(x for x in receipt.approved_scope_ceiling.new_logical_targets if x.target == "SavingAccount")
    assert logical.parent == "BankAccount"
    assert all(x.file == "bank.java" and any(row[0] == x.file and row[1] == x.owner
        and row[2] == inputs["current_context"].source_fingerprint for row in receipt.source_bindings)
        for x in receipt.approved_scope_ceiling.existing_targets)
    assert next(x for x in receipt.approved_scope_ceiling.existing_targets
                if x.target == "BankAccount::saving").declaration_fingerprint
    assert receipt.fingerprint == sha256(json.dumps(receipt.as_dict(), sort_keys=True,
        ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    assert validate_structural_scope_approval_receipt(receipt.as_dict(), stored_human_action=action, **inputs) == receipt
    _safe(receipt)
    assert before == (p1.to_json(), p0.to_json(), inputs["current_source"])


@pytest.fixture
def root_tmp_path(tmp_path):
    return tmp_path


@pytest.mark.parametrize("decision", tuple(DECISIONS))
def test_decisions_are_immutable_and_idempotent(tmp_path, decision):
    inputs = _inputs(tmp_path)
    action = _action(inputs, decision, "Keep this as a bounded revision note." if decision == "request_scope_revision" else "")
    receipt = decide_structural_scope_ceiling(**inputs, human_action=action)
    retry = decide_structural_scope_ceiling(**inputs, human_action=action, previous_receipt=receipt)
    assert receipt == retry and receipt.fingerprint == retry.fingerprint
    assert receipt.eligible_for_admission is (decision == "approve_exact_scope_ceiling")
    assert validate_structural_scope_approval_receipt(receipt, stored_human_action=action,
                                                    require_eligible=False, **inputs) == receipt
    if not receipt.eligible_for_admission:
        with pytest.raises(ValueError, match="not_eligible"):
            validate_structural_scope_approval_receipt(receipt, stored_human_action=action, **inputs)
    with pytest.raises(FrozenInstanceError):
        receipt.write_authority = True
    with pytest.raises((ValueError, TypeError)):
        replace(receipt, write_authority=True)
    _safe(receipt)


@pytest.mark.parametrize("first,second", [("approve_exact_scope_ceiling", "decline_scope_expansion"),
    ("decline_scope_expansion", "approve_exact_scope_ceiling")])
def test_conflicting_retries_never_overwrite(tmp_path, first, second):
    inputs = _inputs(tmp_path)
    receipt = decide_structural_scope_ceiling(**inputs, human_action=_action(inputs, first))
    before = receipt.as_dict()
    with pytest.raises(ValueError, match="conflicting_human_scope_decision"):
        decide_structural_scope_ceiling(**inputs, human_action=_action(inputs, second), previous_receipt=receipt)
    with pytest.raises(ValueError, match="conflicting_human_scope_decision"):
        validate_structural_scope_approval_receipt(receipt, stored_human_action=_action(inputs, first),
            conflicting_action=_action(inputs, second), require_eligible=False, **inputs)
    assert before == receipt.as_dict()


def test_historical_p0_and_non_fixpoint_are_unavailable(tmp_path):
    inputs = _inputs(tmp_path)
    action = _action(inputs)
    with pytest.raises(ValueError, match="historical_proposal_not_approvable"):
        decide_structural_scope_ceiling(**{**inputs, "proposal": inputs["historical_proposal"]}, human_action=action)
    for flag in (False, 1, "true"):
        with pytest.raises(ValueError, match="approval_unavailable"):
            prepare_structural_scope_review(**{**inputs, "refresh_result": replace(inputs["refresh_result"],
                                                                              structural_semantic_fixpoint=flag)})
    post = inputs["refresh_result"].post_refresh_recheck
    post["status"] = "clarification_required"
    post["possible_intent_gaps"] = [{"question": "A new human semantic question"}]
    with pytest.raises(ValueError, match="approval_unavailable"):
        prepare_structural_scope_review(**{**inputs, "refresh_result": replace(inputs["refresh_result"],
            post_refresh_recheck_json=json.dumps(post, sort_keys=True, separators=(",", ":")))})


@pytest.mark.parametrize("change", ("source", "semantics", "repository", "scope", "proposal", "context"))
def test_changed_or_forged_bindings_reject_before_and_after_approval(tmp_path, change):
    inputs = _inputs(tmp_path)
    action = _action(inputs)
    receipt = decide_structural_scope_ceiling(**inputs, human_action=action)
    before = receipt.as_dict()
    bad = dict(inputs)
    if change == "source":
        bad["current_source"] += b"\n// stale"
    elif change == "semantics":
        other = _inputs(tmp_path, "preserve_base_compatibility")
        bad["scope_transition_effective_design"] = other["scope_transition_effective_design"]
    elif change == "repository":
        bad["repository_id"] = "different-repository"
    elif change == "scope":
        from core.repair_scope import RepairScope
        bad["current_scope"] = RepairScope(status="not_applicable", primary_file="bank.java", primary_symbol="saving")
    elif change == "context":
        bad["current_context"] = replace(inputs["current_context"], file="wrong.java")
    else:
        bad["proposal"] = replace(inputs["proposal"], blast_radius=("member",))
        bad["refresh_result"] = replace(inputs["refresh_result"], proposal=bad["proposal"])
    with pytest.raises((ValueError, TypeError)):
        decide_structural_scope_ceiling(**bad, human_action=action)
    with pytest.raises((ValueError, TypeError)):
        validate_structural_scope_approval_receipt(receipt, stored_human_action=action, **bad)
    assert before == receipt.as_dict()


def test_receipt_and_review_cannot_be_replayed_to_another_transition(tmp_path):
    inputs = _inputs(tmp_path)
    action = _action(inputs)
    receipt = decide_structural_scope_ceiling(**inputs, human_action=action)
    other = _inputs(tmp_path, "subclass_specialization")
    with pytest.raises(ValueError, match="binding_mismatch"):
        decide_structural_scope_ceiling(**other, human_action=action)
    with pytest.raises(ValueError):
        validate_structural_scope_approval_receipt(receipt, stored_human_action=_action(other), **other)
    with pytest.raises(ValueError, match="binding_mismatch"):
        decide_structural_scope_ceiling(**inputs, human_action=replace(action, review_fingerprint="a" * 64))


@pytest.mark.parametrize("untrusted", [None, "yes", {"confidence": 1.0}, {"provenance": "model"},
    {"original_task": "Implement SavingAccount"}, {"harness": "approve_exact_scope_ceiling"}])
def test_no_model_task_confidence_or_self_approval(tmp_path, untrusted):
    inputs = _inputs(tmp_path)
    with pytest.raises(ValueError, match="explicit_human_scope_action_required"):
        decide_structural_scope_ceiling(**inputs, human_action=untrusted)


@pytest.mark.parametrize("provenance,channel", [("model", "scope_review_post"),
    ("explicit_human", "generate_patch"), ("explicit_human", "semantic_answer"),
    ("harness", "scope_review_post"), ("explicit_human", "author")])
def test_human_action_requires_approval_boundary(tmp_path, provenance, channel):
    with pytest.raises(ValueError, match="explicit_human"):
        replace(_action(_inputs(tmp_path)), provenance=provenance, channel=channel)


@pytest.mark.parametrize("field,value", [("schema_version", "future"), ("write_authority", True),
    ("apply_authority", 1), ("eligible_for_admission", 1), ("proposal_fingerprint", "a" * 64),
    ("approved_scope_ceiling_fingerprint", "a" * 64), ("status", "implementation_authorized")])
def test_pure_validator_rejects_forged_receipt(tmp_path, field, value):
    inputs = _inputs(tmp_path)
    action = _action(inputs)
    forged = decide_structural_scope_ceiling(**inputs, human_action=action).as_dict()
    forged[field] = value
    with pytest.raises(ValueError, match="stale_or_forged"):
        validate_structural_scope_approval_receipt(forged, stored_human_action=action, **inputs)


def test_ceiling_presentation_preserves_may_and_deferred_semantics(tmp_path):
    for transition in TRANSITION_ANSWERS:
        inputs = _inputs(tmp_path, transition)
        summary = prepare_structural_scope_review(**inputs).presentation
        assert summary["blast_radius"] == list(inputs["proposal"].blast_radius)
        assert any(x["target"] == "BankAccount::successful_balance_debit_capability" for x in summary["possible_api_changes"])
        assert any(x["certainty"] == "MUST_SUPPORT" for x in summary["required_capabilities"])
        assert summary["deferred_implementation"]
        assert "delete" not in summary["transition_summary"].lower()
        assert "override" not in summary["transition_summary"].lower()
        assert "abstract" not in summary["transition_summary"].lower()
        if transition == "preserve_base_compatibility":
            assert "remains semantically required" in summary["transition_summary"]
        if transition == "subclass_specialization":
            assert "common base savings contract remains" in summary["transition_summary"]


def test_approval_has_no_provider_author_file_io_or_traversal(tmp_path):
    inputs = _inputs(tmp_path)
    action = _action(inputs)
    def forbidden(*_a, **_kw):
        raise AssertionError("approval attempted provider, author, file I/O or traversal")
    targets = ("core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "core.control_engine.build_control_prompt", "core.control_engine.authoring_context_for_control_result",
        "socket.create_connection", "socket.socket.connect", "subprocess.run", "subprocess.Popen",
        "os.system", "os.walk", "os.scandir", "os.listdir", "pathlib.Path.open", "pathlib.Path.read_bytes",
        "pathlib.Path.read_text", "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open")
    with ExitStack() as guards:
        for target in targets:
            guards.enter_context(patch(target, forbidden))
        timings = {}
        receipt = decide_structural_scope_ceiling(**inputs, human_action=action, timings=timings)
        validate_structural_scope_approval_receipt(receipt, stored_human_action=action, timings=timings, **inputs)
    assert set(timings) == set(TIMING_FIELDS) and all(t >= 0 for t in timings.values())
    _safe(receipt)


def _web_review(state, transition="savings_only_on_subclass"):
    from web.structural_scope_approval import register_scope_approval_review
    from web.session_store import find_session
    inputs = _inputs(state.repo, transition)
    (state.repo / "bank.java").write_bytes(inputs["current_source"])
    session_id = register_scope_approval_review(**inputs)
    return find_session(session_id), inputs


def _post(state, session, decision="approve_exact_scope_ceiling", **overrides):
    result = session["result"]
    return state.app.test_client().post("/scope_approval/decision", json={
        "session_id": session["id"], "repo_path": session["repo_path"],
        "proposal_fingerprint": result["scope_approval_review"]["proposal_fingerprint"],
        "review_fingerprint": result["review_fingerprint"], "decision": decision, **overrides})


@pytest.mark.parametrize("transition", tuple(TRANSITION_ANSWERS))
@pytest.mark.parametrize("decision", tuple(DECISIONS))
def test_durable_ui_actions_and_read_only_reload(web, monkeypatch, transition, decision):
    from web import session_store
    from web.structural_scope_approval import register_scope_approval_review
    session, inputs = _web_review(web, transition)
    assert register_scope_approval_review(**inputs) == session["id"]
    assert len(session_store.load_sessions()) == 1
    before = session_store.SESSION_FILE.read_bytes()
    source_before = (web.repo / "bank.java").read_bytes()
    # GET reconstructs for validation; it must not invoke the refresh action.
    monkeypatch.setattr("core.structural_scope_refresh.refresh_structural_scope_proposal",
        lambda **_kw: pytest.fail("GET attempted refresh"))
    client = web.app.test_client()
    page = client.get("/session/" + session["id"])
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    for text in ("New logical structure", "SavingAccount", "savingBalance", "Required capabilities",
        "Existing structure potentially affected", "API-surface risk", "Structural blast radius",
        "Implementation details still deferred", "Approval does not write or apply code",
        "Approve exact scope ceiling", "Decline scope expansion", "Request scope revision"):
        assert text in body
    assert 'onclick="applyPatch()" hidden disabled' in body
    assert session_store.SESSION_FILE.read_bytes() == before
    response = _post(web, session, decision, note="<script>revision only</script>" if decision == "request_scope_revision" else "")
    assert response.status_code == 200, response.json
    payload = response.json
    assert payload["status"] == DECISIONS[decision]
    receipt = payload["scope_approval_receipt"]
    assert receipt["eligible_for_admission"] is (decision == "approve_exact_scope_ceiling")
    assert receipt["candidate"] is None and receipt["patch"] == ""
    assert receipt["repair_scope_delta"] == receipt["authoring_scope_delta"] == 0
    saved = session_store.find_session(session["id"])
    assert saved["scope_approval_human_action"]["channel"] == "scope_review_post"
    assert saved["events"] == ["scope_proposal_awaiting_approval", DECISIONS[decision]]
    stored_after = session_store.SESSION_FILE.read_bytes()
    assert _post(web, session, decision, note="<script>revision only</script>" if decision == "request_scope_revision" else "").json == payload
    assert session_store.SESSION_FILE.read_bytes() == stored_after
    page_after = client.get("/session/" + session["id"])
    assert page_after.status_code == 200 and 'id="scopeApprovalForm"' not in page_after.get_data(as_text=True)
    assert client.get("/history/sessions").status_code == 200
    assert session_store.SESSION_FILE.read_bytes() == stored_after
    assert (web.repo / "bank.java").read_bytes() == source_before
    assert not (web.repo / "SavingAccount.java").exists()
    assert web.calls == []


@pytest.mark.parametrize("first,second", [("approve_exact_scope_ceiling", "decline_scope_expansion"),
    ("decline_scope_expansion", "approve_exact_scope_ceiling")])
def test_web_conflict_does_not_change_history(web, first, second):
    from web import session_store
    session, _ = _web_review(web)
    assert _post(web, session, first).status_code == 200
    before = session_store.SESSION_FILE.read_bytes()
    response = _post(web, session, second)
    assert response.status_code == 409 and response.json["code"] == "conflicting_human_scope_decision"
    assert session_store.SESSION_FILE.read_bytes() == before


@pytest.mark.parametrize("change", ("source", "scope", "semantics", "proposal", "display", "authority", "repository"))
def test_web_revalidates_before_submission_and_preserves_history(web, change):
    from web import session_store
    session, _ = _web_review(web)
    altered = deepcopy(session)
    if change == "source":
        (web.repo / "bank.java").write_bytes(b"changed")
    elif change == "scope":
        altered["scope_approval_current_binding"]["current_scope_fingerprint"] = "a" * 64
    elif change == "semantics":
        altered["scope_approval_current_binding"]["effective_design_fingerprint"] = "a" * 64
    elif change == "proposal":
        altered["scope_approval_current_binding"]["proposal_fingerprint"] = "a" * 64
    elif change == "display":
        altered["result"]["scope_approval_review"]["blast_radius"] = ["member"]
    elif change == "authority":
        altered["result"]["write_authority"] = True
    else:
        altered["scope_approval_current_binding"]["repository_id"] = "different"
    session_store.save_sessions([altered])
    before = session_store.SESSION_FILE.read_bytes()
    response = _post(web, session)
    assert response.status_code == 409
    assert session_store.find_session(session["id"])["result"]["scope_approval_receipt"] is None
    assert session_store.SESSION_FILE.read_bytes() == before


def test_approved_history_survives_stale_source_but_eligibility_fails(web):
    from web import session_store
    session, _ = _web_review(web)
    assert _post(web, session).status_code == 200
    before = session_store.SESSION_FILE.read_bytes()
    (web.repo / "bank.java").write_bytes(b"changed after approval")
    client = web.app.test_client()
    page = client.get("/session/" + session["id"])
    assert page.status_code == 200 and "review is stale" in page.get_data(as_text=True)
    assert 'id="scopeApprovalForm"' not in page.get_data(as_text=True)
    assert _post(web, session).status_code == 409
    assert session_store.SESSION_FILE.read_bytes() == before


def test_web_rejects_partial_model_confidence_and_free_text_actions(web):
    session, _ = _web_review(web)
    for fields in ({"decision": "yes"}, {"targets": ["SavingAccount"]},
        {"provenance": "model"}, {"confidence": "1"}, {"write_authority": "true"}):
        assert _post(web, session, **fields).status_code in {400, 409}


def test_existing_origin_csrf_auth_and_host_guards_apply(web):
    from web import session_store
    session, _ = _web_review(web)
    client = web.app.test_client()
    body = client.get("/session/" + session["id"], base_url="http://localhost:5000").get_data(as_text=True)
    token = CSRF_META.search(body).group(1)
    data = {"session_id": session["id"], "repo_path": session["repo_path"],
        "proposal_fingerprint": session["result"]["scope_approval_review"]["proposal_fingerprint"],
        "review_fingerprint": session["result"]["review_fingerprint"], "decision": "approve_exact_scope_ceiling"}
    before = session_store.SESSION_FILE.read_bytes()
    for headers in ({"Origin": "http://localhost:5000"},
        {"Origin": "http://attacker.invalid", "X-CSRF-Token": token}):
        assert client.post("/scope_approval/decision", json=data, headers=headers,
                           base_url="http://localhost:5000").status_code == 403
    assert session_store.SESSION_FILE.read_bytes() == before
    assert client.get("/session/" + session["id"], base_url="http://localhost:5000",
                      headers={"Host": "attacker.invalid:5000"}).status_code == 421
    response = client.post("/scope_approval/decision", json=data,
        headers={"Origin": "http://localhost:5000", "X-CSRF-Token": token}, base_url="http://localhost:5000")
    assert response.status_code == 200, response.json


@pytest.mark.parametrize("authoring", (False, True))
def test_approval_preserves_existing_measured_and_authoring_scope(tmp_path, authoring):
    from dataclasses import asdict
    from core.structural_scope_expansion import propose_structural_scope_expansion, scope_fingerprint
    from core.scope_semantic_recheck import (
        recheck_scope_semantics, make_stored_scope_transition_gap, continue_scope_transition,
        compose_scope_transition_design,
    )
    from core.oop_intent_session import bind_human_answer
    from scripts.replay_patch_scope_expand1 import fixture_inputs
    from tests.test_patch_scope_expand1 import _repair
    base = fixture_inputs(repository_root=tmp_path, source=MEASURED_BANK)
    scope = _repair(base, member="withdraw", authoring=authoring)
    before = asdict(scope)
    parent = dict(task_contract=base["task_contract"], design_intent=base["design_intent"],
        semantic_detection=base["detection"], current_context=base["current_context"],
        current_source=base["current_source"], repository_id=base["repository_id"],
        current_scope=scope, expected_scope_fingerprint=scope_fingerprint(scope), related_contexts=())
    p0 = propose_structural_scope_expansion(**parent).proposal
    recheck_inputs = dict(proposal=p0, **parent, repo_path=base["repo_path"],
                         stored_gap=base["stored_gap"], stored_answer=base["stored_answer"])
    gap = make_stored_scope_transition_gap(recheck_scope_semantics(**recheck_inputs),
        task_contract=base["task_contract"], current_context=base["current_context"], repository_id=base["repository_id"])
    answer = bind_human_answer(gap, TRANSITION_ANSWERS["savings_only_on_subclass"]).as_dict()
    continuation = continue_scope_transition(**recheck_inputs, stored_transition_gap=gap, stored_transition_answer=answer)
    recheck = recheck_scope_semantics(**recheck_inputs, transition_continuation=continuation,
                                    stored_transition_gap=gap, stored_transition_answer=answer)
    inputs = _inputs(tmp_path)
    inputs.update(historical_proposal=p0, current_scope=scope, expected_scope_fingerprint=scope_fingerprint(scope),
        transition_continuation=continuation, stored_transition_gap=gap, stored_transition_answer=answer,
        scope_transition_effective_design=compose_scope_transition_design(base["design_intent"], continuation),
        validated_recheck_receipt=recheck)
    args = {k: v for k, v in inputs.items() if k not in {"proposal", "refresh_result"}}
    refreshed = _refresh(args)
    inputs.update(proposal=refreshed.proposal, refresh_result=refreshed)
    action = _action(inputs)
    receipt = decide_structural_scope_ceiling(**inputs, human_action=action)
    assert receipt.current_scope_fingerprint == scope_fingerprint(scope)
    assert validate_structural_scope_approval_receipt(receipt, stored_human_action=action, **inputs) == receipt
    assert asdict(scope) == before
    _safe(receipt)


def test_concurrent_identical_actions_have_one_durable_decision(web):
    from concurrent.futures import ThreadPoolExecutor
    from web import session_store
    session, _ = _web_review(web)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: _post(web, session), range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json == responses[1].json
    assert session_store.find_session(session["id"])["events"] == [
        "scope_proposal_awaiting_approval", "approved_for_scope_admission"]


def test_revision_note_is_bounded_and_never_semantically_interpreted(tmp_path):
    inputs = _inputs(tmp_path)
    action = _action(inputs, "request_scope_revision", "Change everything.\r\n<script>alert(1)</script>")
    receipt = decide_structural_scope_ceiling(**inputs, human_action=action)
    assert action.note == "Change everything.\n<script>alert(1)</script>"
    assert receipt.effective_design_fingerprint == inputs["proposal"].effective_design_fingerprint
    for note in ("x" * 1001, "unsafe\x00note"):
        with pytest.raises(ValueError, match="invalid_scope_revision_note"):
            replace(action, note=note)
    _safe(receipt)


def test_attached_semantic_session_retains_chain_and_rejects_later_semantic_changes(web):
    from tests.test_patch_scope_recheck1 import _web_wait, _web_answer
    from web import session_store
    from web.structural_scope_approval import register_scope_approval_review
    waiting, _ = _web_wait(web)
    original = session_store.find_session(waiting["clarification_session_id"])
    resolved = _web_answer(web, original, TRANSITION_ANSWERS["savings_only_on_subclass"])
    assert resolved["status"] == "clarification_projected"
    semantic_session = session_store.find_session(original["id"])
    saved_chain = deepcopy(semantic_session["result"]["scope_transition_continuation"])
    inputs = _inputs(web.repo)
    session_id = register_scope_approval_review(**inputs, session_id=semantic_session["id"])
    assert session_id == semantic_session["id"] and len(session_store.load_sessions()) == 1
    review_session = session_store.find_session(session_id)
    assert review_session["result"]["scope_transition_continuation"] == saved_chain
    assert _post(web, review_session).status_code == 200
    approved = session_store.find_session(session_id)
    receipt_before = deepcopy(approved["result"]["scope_approval_receipt"])
    approved["result"]["effective_design_intent"]["effective_design_fingerprint"] = "a" * 64
    session_store.save_sessions([approved])
    before = session_store.SESSION_FILE.read_bytes()
    response = _post(web, review_session)
    assert response.status_code == 409 and response.json["code"] == "approval_stale"
    assert session_store.find_session(session_id)["result"]["scope_approval_receipt"] == receipt_before
    assert session_store.SESSION_FILE.read_bytes() == before
