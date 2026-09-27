"""Offline Generate/continuation regression for the semantic wait handoff."""
from __future__ import annotations

from copy import deepcopy
import json

from tests.test_repair_intent1 import TASK, _evidence


def _harness(monkeypatch, tmp_path, *, resumed=None):
    from web import app as wa
    from web import session_store

    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(wa, "_patch_generation_harness_block", lambda *_: None)
    prompts = []

    def prompt(control, task, **kwargs):
        prompts.append((task, "initial"))
        return "AUTHOR PROMPT"

    monkeypatch.setattr(wa, "build_control_prompt", prompt)
    control, author = _evidence(tmp_path)
    calls = []

    def model(prompt_text):
        calls.append(prompt_text)
        if len(calls) == 1:
            return json.dumps(author)
        if resumed is None:
            return json.dumps({"patch_candidate": None, "needs_escalation": True})
        return json.dumps(resumed)

    monkeypatch.setattr(wa, "run_gemini_request", model)
    monkeypatch.setattr(wa, "enforce_control_grounding_on_payload", lambda *_: None)
    with wa.app.test_request_context("/generate_patch", method="POST",
                                     data={"repo_path": str(tmp_path)}):
        waiting = wa._generate_patch_from_control(str(tmp_path), control)
    assert waiting["status"] == "waiting_for_clarification"
    assert waiting["patch"] == ""
    assert waiting["write_authority"] is False
    assert waiting["execution_authorized"] is False
    assert len(calls) == 1
    return wa, session_store, waiting, calls


def _answer(wa, wait, repo, text="Use shared static state", decline=False):
    with wa.app.test_request_context("/repair_intent/answer", method="POST", data={
        "session_id": wait["clarification_session_id"], "repo_path": str(repo),
        "answer": text, "decline": "true" if decline else "false",
    }):
        return wa.answer_repair_intent()


def test_wait_persists_then_resumes_same_task_with_human_section(monkeypatch, tmp_path):
    resumed = {"patch_candidate": {"file": "MainApp.java", "target_snippet": "old",
                                   "patched_snippet": "new"},
               "human_clarification_ack": "Use shared static state"}
    wa, store, wait, calls = _harness(monkeypatch, tmp_path, resumed=resumed)
    session = store.find_session(wait["clarification_session_id"])
    assert session["query"] == TASK
    assert session["status"] == "waiting_for_clarification"
    assert session["events"] == ["waiting_for_clarification"]
    result = _answer(wa, wait, tmp_path)
    assert result["status"] == "resumed"
    assert "patched_snippet" in result["patch"]
    assert result["write_authority"] is False
    assert result["execution_authorized"] is False
    assert len(calls) == 2
    assert "[HUMAN CLARIFICATION]" in calls[1]
    assert '"Use shared static state"' in calls[1]
    session = store.find_session(wait["clarification_session_id"])
    assert session["events"] == ["waiting_for_clarification", "clarification_supplied", "resumed"]
    assert session["clarification_answer"]["provenance"] == "human_provided_semantic_evidence"
    assert _answer(wa, wait, tmp_path) == result
    assert len(calls) == 2  # duplicate answer never makes another model call
    conflict = _answer(wa, wait, tmp_path, "Use instance state")
    assert conflict[1] == 409 and conflict[0]["code"] == "clarification_conflict"


def test_stale_source_reacquires_instead_of_authoring(monkeypatch, tmp_path):
    wa, store, wait, calls = _harness(monkeypatch, tmp_path)
    source = tmp_path / "MainApp.java"
    source.write_text(source.read_text(encoding="utf-8") + "// changed\n", encoding="utf-8")
    result = _answer(wa, wait, tmp_path)
    assert result[1] == 409
    assert result[0]["status"] == "reacquisition_required"
    assert result[0]["code"] == "stale_source"
    assert len(calls) == 1
    session = store.find_session(wait["clarification_session_id"])
    assert session["clarification_answer"]["text"] == "Use shared static state"


def test_wrong_repository_and_decline_never_author(monkeypatch, tmp_path):
    wa, store, wait, calls = _harness(monkeypatch, tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    result = _answer(wa, wait, other)
    assert result[1] == 409 and result[0]["code"] == "wrong_repository"
    declined = _answer(wa, wait, tmp_path, decline=True)
    assert declined["status"] == "clarification_declined"
    assert declined["patch"] == ""
    assert len(calls) == 1
    assert store.find_session(wait["clarification_session_id"])["status"] == "clarification_declined"


def test_author_must_acknowledge_exact_human_text(monkeypatch, tmp_path):
    wa, _, wait, calls = _harness(monkeypatch, tmp_path, resumed={
        "patch_candidate": {"file": "MainApp.java", "patched_snippet": "guess"},
        "human_clarification_ack": "a different meaning",
    })
    result = _answer(wa, wait, tmp_path, "Neither. I intended <script>x</script>.")
    assert result["status"] == "intent_preservation_failed"
    assert result["patch"] == ""
    assert len(calls) == 2
    assert "<script>x</script>" in calls[1]
