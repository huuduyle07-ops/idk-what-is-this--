"""REPAIR.INTENT.UI.1: persisted clarification is a session presentation state."""
from __future__ import annotations

import json
from copy import deepcopy

from tests.test_auth_web1 import web
from tests.test_ux_state1_browser import live, chromium, _load, _snapshot, _candidate
from web.session_presentation import project_session


SESSION_ID = "repair-intent-waiting-fixture"
QUESTION = "Which state owns <value> & the output?"
ALTERNATIVES = ["Keep <value> local", "Use shared & state"]


def _waiting(repo):
    return {
        "id": SESSION_ID,
        "title": "Clarify repair",
        "query": "Repair MainApp.java",
        "repo_path": str(repo),
        "mode": "repair_intent",
        "web_mode": "instant",
        "status": "waiting_for_clarification",
        "repair_intent_gap": {
            "status": "waiting_for_clarification",
            "question": QUESTION,
            "alternatives": [{"description": value} for value in ALTERNATIVES],
        },
        "clarification_answer": None,
        "events": ["waiting_for_clarification"],
        "result": {"answer": "stale result text", "patch": "", "status": "waiting_for_clarification",
                   "write_authority": False, "execution_authorized": False},
    }


def _save(session):
    from web import session_store
    session_store.save_sessions([session])


def test_waiting_session_http_uses_authoritative_gap_and_id_without_mutation(web):
    from web import session_store
    session = _waiting(web.repo)
    _save(session)
    before = session_store.SESSION_FILE.read_bytes()
    client = web.app.test_client()
    for _ in range(2):
        response = client.get(f"/session/{SESSION_ID}")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Which state owns &lt;value&gt; &amp; the output?" in body
        assert "Keep &lt;value&gt; local" in body
        assert "Use shared &amp; state" in body
        assert "stale result text" not in body
        assert f'sessionId: "{SESSION_ID}"' in body
        assert 'onclick="applyPatch()" hidden disabled' in body
        assert 'onclick="showTab(\'patch\')" hidden disabled' in body
        assert "result.clarification_session_id" not in body
    assert session_store.SESSION_FILE.read_bytes() == before
    assert len(session_store.load_sessions()) == 1
    assert web.calls == []


def test_normal_candidate_nonpatch_and_terminal_clarifications_render(web):
    client = web.app.test_client()
    candidate = _waiting(web.repo)
    candidate.update(id="candidate", status="resumed", repair_intent_gap=None)
    candidate["result"] = {"answer": "patch ready", "patch": json.dumps({"summary": "candidate"})}
    _save(candidate)
    body = client.get("/session/candidate").get_data(as_text=True)
    assert "patch ready" in body and "repairIntentClarification\" hidden" in body
    assert 'onclick="applyPatch()" hidden disabled' not in body
    assert "candidate" in body

    for status in ("clarification_declined", "reacquisition_required", "intent_preservation_failed"):
        terminal = deepcopy(candidate)
        terminal["id"] = status
        terminal["status"] = status
        terminal["result"] = {"answer": status, "patch": "", "status": status}
        _save(terminal)
        response = client.get(f"/session/{status}")
        assert response.status_code == 200
        assert status in response.get_data(as_text=True)

    chat = {"id": "chat", "query": "hello", "repo_path": str(web.repo),
            "mode": "retrieve", "web_mode": "chat", "result": {"answer": "hello back"}}
    _save(chat)
    assert client.get("/session/chat").status_code == 200


def test_missing_and_malformed_waiting_sessions_are_safe(web):
    client = web.app.test_client()
    assert client.get("/session/unknown").status_code == 404
    broken = _waiting(web.repo)
    broken["repair_intent_gap"] = {"alternatives": []}
    _save(broken)
    response = client.get(f"/session/{SESSION_ID}")
    assert response.status_code == 422
    assert "missing its clarification question" in response.get_data(as_text=True)
    broken = _waiting(web.repo)
    broken["result"]["patch"] = '{"patch_candidate": {"file": "MainApp.java"}}'
    _save(broken)
    assert client.get(f"/session/{SESSION_ID}").status_code == 422
    assert web.calls == []


def test_projection_accepts_missing_optional_alternatives():
    waiting = _waiting("C:/repo")
    del waiting["repair_intent_gap"]["alternatives"]
    projection = project_session(waiting)
    assert projection["session_id"] == SESSION_ID
    assert projection["status"] == "waiting_for_clarification"
    assert projection["clarification"] == {
        "session_id": SESSION_ID, "question": QUESTION, "alternatives": (),
    }
    assert "clarification_session_id" not in waiting["result"]


def test_browser_waiting_session_has_question_real_id_and_no_candidate(live):
    _save(_waiting(live.repo_a))
    _load(live, f"/session/{SESSION_ID}")
    page = live.page
    assert page.locator("#answer").is_visible()
    assert page.locator("#answer").text_content() == QUESTION
    assert page.locator("#repairIntentClarification").is_visible()
    assert page.locator("#repairIntentAlternatives li").all_text_contents() == ALTERNATIVES
    page.locator(f'[data-session-id="{SESSION_ID}"] .session-meta').wait_for()
    assert "waiting_for_clarification" in page.locator(f'[data-session-id="{SESSION_ID}"] .session-meta').text_content()
    assert page.locator("#repairIntentAnswer").is_visible()
    assert page.evaluate("() => window.pendingRepairIntent.sessionId") == SESSION_ID
    assert _snapshot(page)["candidate"] is None
    assert _candidate(page).raw == ""
    assert page.locator('button[onclick="applyPatch()"]:disabled').count() == 1
    assert not page.locator('button[onclick="applyPatch()"]').is_visible()
    assert live.posts == []
    _load(live, f"/session/{SESSION_ID}")
    assert live.posts == [] and len(__import__("web.session_store", fromlist=["load_sessions"]).load_sessions()) == 1


def test_browser_candidate_session_keeps_patch_controls(live):
    session = _waiting(live.repo_a)
    session.update(id="candidate", status="resumed", repair_intent_gap=None)
    session["result"] = {"answer": "patch ready", "patch": json.dumps({"summary": "candidate"})}
    _save(session)
    _load(live, "/session/candidate")
    assert not live.page.locator("#repairIntentClarification").is_visible()
    assert live.page.locator('button[onclick="applyPatch()"]:enabled').count() == 1
    assert _snapshot(live.page)["candidate"] is not None


def test_browser_live_wait_disables_patch_actions(live):
    from tests.test_ux_state1_browser import _await_held, _fulfill

    live.hold_paths.add("/generate_patch")
    _load(live)
    page = live.page
    page.fill("#repoPathInput", str(live.repo_a))
    page.locator('textarea[name="query"]').fill("Repair MainApp.java")
    page.locator('button[onclick="generatePatch()"]').click()
    _fulfill(live, _await_held(live, "/generate_patch", 1), {
        "status": "waiting_for_clarification", "question": QUESTION,
        "clarification_session_id": SESSION_ID, "patch": "",
    })
    assert page.locator("#repairIntentClarification").is_visible()
    assert page.evaluate("() => window.pendingRepairIntent.sessionId") == SESSION_ID
    assert _snapshot(page)["candidate"] is None
    assert not page.locator('button[onclick="applyPatch()"]').is_visible()
    assert page.locator('button[onclick="applyPatch()"]:disabled').count() == 1
    assert live.posts == ["/generate_patch"]


def test_browser_missing_optional_alternatives_and_malformed_question(live):
    waiting = _waiting(live.repo_a)
    del waiting["repair_intent_gap"]["alternatives"]
    _save(waiting)
    _load(live, f"/session/{SESSION_ID}")
    assert live.page.locator("#repairIntentClarification").is_visible()
    assert live.page.locator("#repairIntentAlternatives li").count() == 0
    waiting["repair_intent_gap"].pop("question")
    _save(waiting)
    assert live.page.goto(f"{live.base}/session/{SESSION_ID}").status == 422
