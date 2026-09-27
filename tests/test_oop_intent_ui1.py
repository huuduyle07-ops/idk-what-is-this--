"""OOP.INTENT.UI.1: durable, candidate-free semantic review clarification."""
from __future__ import annotations

from copy import deepcopy
import time

from tests.test_auth_web1 import web
from tests.test_ctx_oop_1c import BANK, COUNTER, review
from tests.test_ux_state1_browser import live, chromium, _load, _snapshot

from core.oop_intent_session import make_stored_gap
from web.session_presentation import project_session


TASK = "Review BankAccount logic; is saving correct?"


def _waiting(repo, *, task=TASK, source=BANK):
    from web.session_store import create_oop_intent_wait, find_session
    (repo / "bank.java").write_bytes(source.encode("utf-8"))
    result, _ = review(source, task)
    gap = make_stored_gap(result, task_text=task, repo_path=str(repo))
    if gap is None:
        return None
    session_id = create_oop_intent_wait(repo_path=str(repo), task_text=task, stored_gap=gap)
    return find_session(session_id)


def _answer(app, session, text="Saving uses the same balance.", *, decline=False,
            gap_id=None, session_id=None, repo_path=None):
    with app.test_request_context("/oop_intent/answer", method="POST", data={
        "session_id": session_id or session["id"],
        "gap_id": gap_id or session["oop_intent_gap"]["gap_id"],
        "repo_path": repo_path or session["repo_path"],
        "answer": text, "decline": "true" if decline else "false",
    }):
        from web.app import answer_oop_intent
        return answer_oop_intent()


def test_bank_wait_http_history_and_candidate_free(web):
    from web import session_store
    session = _waiting(web.repo)
    assert session["clarification_kind"] == "oop_intent"
    assert session["status"] == "waiting_for_clarification"
    assert len(session_store.load_sessions()) == 1
    assert _waiting(web.repo)["id"] == session["id"]
    before = session_store.SESSION_FILE.read_bytes()
    client = web.app.test_client()
    response = client.get("/session/" + session["id"])
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "balance is instance state" in body
    assert "Why this may matter" in body
    assert "not a proven defect" in body
    assert "Should saving use this same balance" in body
    assert "Saving applies to the current account balance" in body
    assert "Savings has separate state" in body
    assert 'onclick="applyPatch()" hidden disabled' in body
    assert session["id"] in body
    assert session_store.SESSION_FILE.read_bytes() == before
    assert client.get("/session/missing").status_code == 404
    malformed = deepcopy(session)
    malformed["oop_intent_gap"]["question"] = "changed"
    session_store.save_sessions([malformed])
    assert client.get("/session/" + session["id"]).status_code == 422
    assert web.calls == []


def test_review_form_enters_one_real_wait_without_provider(web, monkeypatch):
    from web import session_store
    (web.repo / "bank.java").write_bytes(BANK.encode("utf-8"))
    monkeypatch.setattr(web.wa, "retrieve_context", lambda *a, **k: "")
    response = web.app.test_client().post("/", data={
        "query": TASK, "repo_path": str(web.repo), "mode": "retrieve",
    })
    assert response.status_code == 200
    sessions = session_store.load_sessions()
    assert len(sessions) == 1
    assert sessions[0]["clarification_kind"] == "oop_intent"
    assert sessions[0]["status"] == "waiting_for_clarification"
    assert sessions[0]["result"]["patch"] == ""
    assert "Should saving use this same balance" in response.get_data(as_text=True)
    assert web.calls == []


def test_answer_binding_retry_conflict_stale_and_decline(web):
    from web import session_store
    session = _waiting(web.repo)
    wrong = _answer(web.app, session, gap_id="0" * 64)
    assert wrong[1] == 409 and wrong[0]["code"] == "wrong_gap"
    wrong = _answer(web.app, session, session_id="missing")
    assert wrong[1] == 404
    first = _answer(web.app, session, "<same & balance>")
    assert first["status"] == "resumed" and first["patch"] == ""
    assert first["semantic_review_status"] == "informational"
    saved = session_store.find_session(session["id"])
    assert saved["clarification_answer"]["provenance"] == "human_provided_semantic_evidence"
    assert saved["clarification_answer"]["gap_id"] == session["oop_intent_gap"]["gap_id"]
    rendered = web.app.test_client().get("/session/" + session["id"]).get_data(as_text=True)
    assert "&lt;same &amp; balance&gt;" in rendered
    assert "<same & balance>" not in rendered
    assert _answer(web.app, session, "<same & balance>") == first
    assert session_store.find_session(session["id"])["events"] == [
        "waiting_for_clarification", "clarification_supplied", "resumed"]
    conflict = _answer(web.app, session, "Separate savings state")
    assert conflict[1] == 409 and conflict[0]["code"] == "clarification_conflict"
    assert web.calls == []

    session_store.save_sessions([])
    session = _waiting(web.repo)
    (web.repo / "bank.java").write_text(BANK + "\n// changed", encoding="utf-8")
    stale = _answer(web.app, session)
    assert stale[1] == 409 and stale[0]["status"] == "reacquisition_required"
    assert session_store.find_session(session["id"])["clarification_answer"] is None

    session_store.save_sessions([])
    session = _waiting(web.repo)
    declined = _answer(web.app, session, decline=True)
    assert declined["status"] == "clarification_declined"
    assert session_store.find_session(session["id"])["clarification_answer"] is None


def test_informational_educational_and_counter_do_not_wait(web):
    from web.session_store import load_sessions
    explicit = "This is a simple exercise where saving applies interest directly to the same balance. Review it."
    assert _waiting(web.repo, task=explicit) is None
    assert load_sessions() == []
    result, _ = review(COUNTER, "Review Counter behavior", target_name="Counter")
    assert result.status == "informational"
    assert make_stored_gap(result, task_text="Review Counter behavior", repo_path=str(web.repo)) is None
    static = BANK.replace("private double balance", "private static double balance")
    assert _waiting(web.repo, source=static, task="Review realistic account behavior")["clarification_kind"] == "oop_intent"


def test_model_observation_and_task_text_are_html_escaped(web):
    from web.session_store import create_oop_intent_wait
    baseline, _ = review()
    ref = next(ref for ref in baseline.evidence_refs if ref.startswith("field:"))
    report = {"file": baseline.file, "class_identity": baseline.class_identity,
              "source_fingerprint": baseline.source_fingerprint,
              "observations": [{"kind": "domain_state_overlap", "evidence_refs": [ref],
                  "description": "<script>alert('x')</script>",
                  "material_behavior_difference": True}]}
    result, _ = review(model_report=report)
    (web.repo / "bank.java").write_bytes(BANK.encode("utf-8"))
    gap = make_stored_gap(result, task_text=TASK, repo_path=str(web.repo))
    session_id = create_oop_intent_wait(repo_path=str(web.repo), task_text=TASK,
                                        stored_gap=gap)
    body = web.app.test_client().get("/session/" + session_id).get_data(as_text=True)
    assert "&lt;script&gt;alert" in body
    assert "<script>alert('x')</script>" not in body


def test_projection_and_binding_performance(web):
    from core.oop_intent_session import bind_human_answer, validate_stored_gap
    session = _waiting(web.repo)
    gap = session["oop_intent_gap"]
    from web.session_store import create_oop_intent_wait
    start = time.perf_counter()
    for _ in range(100):
        projected = project_session(session)
    projection_ms = (time.perf_counter() - start) * 10
    start = time.perf_counter()
    for _ in range(10):
        create_oop_intent_wait(repo_path=str(web.repo), task_text=TASK,
                               stored_gap=gap)
    persistence_ms = (time.perf_counter() - start) * 100
    client = web.app.test_client()
    start = time.perf_counter()
    for _ in range(10):
        assert client.get("/session/" + session["id"]).status_code == 200
    get_ms = (time.perf_counter() - start) * 100
    start = time.perf_counter()
    for _ in range(100):
        verified = validate_stored_gap(gap, task_text=TASK, repo_path=str(web.repo))
        bind_human_answer(verified, "Same account balance")
    binding_ms = (time.perf_counter() - start) * 10
    assert projected["clarification"]["kind"] == "oop_intent"
    print({"projection_ms": round(projection_ms, 3),
           "persistence_ms": round(persistence_ms, 3),
           "get_ms": round(get_ms, 3), "binding_ms": round(binding_ms, 3)})
    assert max(projection_ms, persistence_ms, get_ms, binding_ms) < 500


def test_patch_task_stops_at_same_oop_gap_before_candidate(web):
    from web.oop_intent_adapter import admit_oop_patch_wait
    from web.session_store import find_session
    (web.repo / "bank.java").write_bytes(BANK.encode("utf-8"))
    task = "Review BankAccount saving behavior and prepare a patch."
    control = {"repair_scope": {"status": "complete",
                                "primary_target": {"file": "bank.java", "symbol": "BankAccount"}}}
    waiting = admit_oop_patch_wait(control=control, repo_path=str(web.repo), task_text=task)
    assert waiting is not None
    assert waiting["status"] == "waiting_for_clarification"
    assert waiting["patch_candidate"] is None and waiting["patch"] == ""
    assert waiting["write_authority"] is False and waiting["execution_authorized"] is False
    session = find_session(waiting["clarification_session_id"])
    assert session["task_mode"] == "patch" and session["oop_intent_gap"]["gap_kind"] == "oop_intent"
    assert web.calls == []


def test_patch_answer_resumes_original_author_without_apply(web, monkeypatch):
    from web.oop_intent_adapter import admit_oop_patch_wait
    from web.session_store import find_session
    from web import app as wa
    import json

    (web.repo / "bank.java").write_bytes(BANK.encode("utf-8"))
    task = "Review BankAccount saving behavior and prepare a patch."
    control = {"repair_scope": {"status": "complete",
                                "primary_target": {"file": "bank.java", "symbol": "BankAccount"}}}
    waiting = admit_oop_patch_wait(control=control, repo_path=str(web.repo), task_text=task)
    session = find_session(waiting["clarification_session_id"])
    prompts = []
    monkeypatch.setattr(wa, "build_control_prompt", lambda *a, **k: "ORIGINAL TASK")
    monkeypatch.setattr(wa, "enforce_control_grounding_on_payload", lambda *a: None)
    def author(prompt):
        prompts.append(prompt)
        return json.dumps({"patch_candidate": {"file": "bank.java", "target_snippet": "old",
                                               "patched_snippet": "new"},
                           "human_clarification_ack": "Separate savings state."})
    monkeypatch.setattr(wa, "run_gemini_request", author)
    original = (web.repo / "bank.java").read_bytes()
    result = _answer(web.app, session, "Separate savings state.")
    assert result["status"] == "resumed"
    assert result["patch"] and result["write_authority"] is False
    assert result["execution_authorized"] is False and result["auto_apply"] is False
    assert "Separate savings state." in prompts[0]
    assert (web.repo / "bank.java").read_bytes() == original
    assert _answer(web.app, session, "Separate savings state.") == result
    assert len(prompts) == 1


def test_browser_waiting_oop_review(live):
    session = _waiting(live.repo_a)
    _load(live, "/session/" + session["id"])
    page = live.page
    assert page.locator("#oopIntentClarification").is_visible()
    assert page.locator("#oopIntentQuestion").is_visible()
    assert page.locator("#oopIntentAlternatives li").count() == 2
    assert page.locator("#oopIntentAnswer").is_visible()
    assert page.locator("#oopIntentClarification").get_by_text("Decline to clarify").is_visible()
    assert page.evaluate("() => window.pendingOOPIntent.sessionId") == session["id"]
    assert _snapshot(page)["candidate"] is None
    assert not page.locator('button[onclick="applyPatch()"]').is_visible()
    assert live.posts == []
