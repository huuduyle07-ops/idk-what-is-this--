"""Deterministic REPAIR.INTENT.ADMIT.1 author-result boundary regressions."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from core.author_escalation_admission import (
    ADMITTED, INCONSISTENT, SEMANTIC, TYPED, UNCLASSIFIED,
    admit_author_escalation,
)
from core.candidate_revision import OUTPUT_AUTHOR_ESCALATION, parse_revised_candidate
from tests.test_candidate_revision_live import _receipt as revision_receipt
from tests.test_repair_intent1 import TASK, _evidence


@pytest.mark.parametrize("candidate,flag,reason,expected", [
    ({"patched_snippet": "x"}, False, None, ADMITTED),
    (None, True, "semantic_intent_required", SEMANTIC),
    ({"patched_snippet": "x"}, True, "semantic_intent_required", SEMANTIC),
    (None, True, "insufficient_evidence", TYPED),
    ({"patched_snippet": "x"}, True, "missing_context", TYPED),
    ({"patched_snippet": "x"}, True, None, UNCLASSIFIED),
    ({"patched_snippet": "x"}, False, "semantic_intent_required", INCONSISTENT),
    ({"patched_snippet": "x"}, True, "made_up", UNCLASSIFIED),
    ({"patched_snippet": "x"}, True, 3, UNCLASSIFIED),
    ({"patched_snippet": "x"}, "true", "missing_context", UNCLASSIFIED),
])
def test_closed_admission_matrix(candidate, flag, reason, expected):
    author = {"patch_candidate": candidate, "needs_escalation": flag,
              "confidence": 0.99}
    if reason is not None:
        author["escalation_reason"] = reason
    decision = admit_author_escalation(author, raw_response=json.dumps(author))
    assert decision.status == expected
    assert decision.admitted is (expected == ADMITTED)
    if candidate is not None and not decision.admitted:
        receipt = decision.quarantine_receipt()
        assert receipt["raw_candidate"] == candidate
        assert receipt["candidate_with_escalation"] is True
        assert len(receipt["candidate_fingerprint"]) == 64
        assert receipt["write_authority"] is False
        assert receipt["execution_authorized"] is False


def _run_web(monkeypatch, tmp_path, author):
    from web import app as wa
    from web import session_store

    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(wa, "_patch_generation_harness_block", lambda *_: None)
    monkeypatch.setattr(wa, "build_control_prompt", lambda *_a, **_k: "AUTHOR PROMPT")
    control, _ = _evidence(tmp_path)
    calls = []
    grounding = []
    monkeypatch.setattr(wa, "run_gemini_request", lambda prompt: calls.append(prompt)
                        or json.dumps(author))
    monkeypatch.setattr(wa, "enforce_control_grounding_on_payload",
                        lambda *_: grounding.append(True))

    def invoke():
        with wa.app.test_request_context("/generate_patch", method="POST",
                                         data={"repo_path": str(tmp_path)}):
            return wa._generate_patch_from_control(str(tmp_path), control)

    return invoke, session_store, calls, grounding, control


def test_live_equivalent_candidate_and_untyped_escalation_is_quarantined(monkeypatch, tmp_path):
    _, author = _evidence(tmp_path)
    author = {"patch_candidate": {"file": "MainApp.java", "patched_snippet": "bad"},
              "confidence": 0.7, "needs_escalation": True}
    invoke, store, calls, grounding, _ = _run_web(monkeypatch, tmp_path, author)
    result = invoke()
    assert result["status"] == UNCLASSIFIED
    assert result["patch"] == "" and result["patch_candidate"] is None
    assert result["author_escalation_receipt"]["raw_candidate"] == author["patch_candidate"]
    assert result["author_escalation_receipt"]["raw_author_response"] == json.dumps(author)
    assert store.load_sessions() == []
    assert grounding == [] and len(calls) == 1


@pytest.mark.parametrize("with_candidate", [False, True])
def test_typed_semantic_escalation_waits_once_with_exact_bindings(
    monkeypatch, tmp_path, with_candidate,
):
    _, author = _evidence(tmp_path)
    if with_candidate:
        author["patch_candidate"] = {"file": "MainApp.java", "patched_snippet": "bad"}
    invoke, store, calls, grounding, control = _run_web(monkeypatch, tmp_path, author)
    first = invoke()
    second = invoke()
    assert first["status"] == second["status"] == "waiting_for_clarification"
    assert first["clarification_session_id"] == second["clarification_session_id"]
    assert first["patch"] == "" and first["patch_candidate"] is None
    assert first["write_authority"] is False
    assert first["execution_authorized"] is False
    sessions = store.load_sessions()
    assert len(sessions) == 1
    session = sessions[0]
    assert session["status"] == "waiting_for_clarification"
    assert session["query"] == TASK
    assert session["control"] == control
    assert session["repair_intent_gap"]["repository_id"] == control["repair_scope"]["repository_id"]
    assert session["repair_intent_gap"]["control_fingerprint"] == control["repair_scope"]["control_fingerprint"]
    assert session["author_escalation_receipt"]["raw_candidate"] == author["patch_candidate"]
    assert grounding == [] and len(calls) == 2  # one existing call per request


@pytest.mark.parametrize("candidate", [None, {"patched_snippet": "bad"}])
def test_nonsemantic_escalation_never_creates_semantic_wait(monkeypatch, tmp_path, candidate):
    _evidence(tmp_path)
    author = {"patch_candidate": candidate, "needs_escalation": True,
              "escalation_reason": "insufficient_evidence"}
    invoke, store, calls, grounding, _ = _run_web(monkeypatch, tmp_path, author)
    result = invoke()
    assert result["status"] == TYPED
    assert result["code"] == "insufficient_evidence"
    assert result["patch"] == "" and result["patch_candidate"] is None
    assert store.load_sessions() == []
    assert grounding == [] and len(calls) == 1


def test_revision_candidate_with_escalation_is_quarantined():
    author = {"patch_candidate": {"patched_snippet": "bad"},
              "needs_escalation": True, "escalation_reason": "missing_context"}
    revised = parse_revised_candidate(json.dumps(author), revision_receipt())
    assert revised.accepted is False
    assert revised.rejection_reason == OUTPUT_AUTHOR_ESCALATION
    assert revised.quarantine_receipt["raw_candidate"] == author["patch_candidate"]
    assert revised.candidate is None


def test_revision_legacy_non_escalated_candidate_keeps_old_parser_result():
    author = {"patch_candidate": {"patched_snippet": "bad"},
              "needs_escalation": False}
    revised = parse_revised_candidate(json.dumps(author), revision_receipt())
    assert revised.rejection_reason != OUTPUT_AUTHOR_ESCALATION
