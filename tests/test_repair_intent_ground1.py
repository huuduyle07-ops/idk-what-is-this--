"""System-owned semantic-gap anchors from the measured current repair set."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from core.repair_intent import RepairIntentGap, admit_gap
from core.repair_intent_evidence_refs import EvidenceRefError
from tests.test_repair_intent1 import TASK, _evidence


SOURCE = ("class MainApp {\r\n"
          "  void m1() {\r\n"
          "    int no1 = 10;   //local variable\r\n"
          "  }\r\n"
          "  void m2() { int no2 = 20; }\r\n"
          "}\r\n")


def _case(root):
    control, author = _evidence(root)
    raw = SOURCE.encode("utf-8")
    (root / "MainApp.java").write_bytes(raw)
    scope = control["repair_scope"]
    scope["source_fingerprint"] = sha256(raw).hexdigest()
    scope["members"] = [
        {"file": "MainApp.java", "symbol": "m1", "kind": "function",
         "span": {"start_line": 2, "end_line": 4},
         "source_snippet": "void m1() {\n    int no1 = 10;   //local variable\n  }",
         "diagnostics": [{"file": "MainApp.java", "line": 3, "col": 5,
                          "severity": "error", "kind": "compiler_error",
                          "message": "cannot find symbol"}],
         "bindings": {"source_path": "MainApp.java", "target_symbol": "m1",
                      "source_sha256": sha256(SOURCE.replace("\r\n", "\n").encode()).hexdigest(),
                      "target_source_sha256": sha256(
                          b"void m1() {\n    int no1 = 10;   //local variable\n  }").hexdigest(),
                      "available_baseline_bindings": [{"name": "no1", "kind": "local"}]}},
        {"file": "MainApp.java", "symbol": "m2", "kind": "function",
         "span": {"start_line": 5, "end_line": 5},
         "source_snippet": "void m2() { int no2 = 20; }", "diagnostics": []},
    ]
    author["semantic_gap"] = {
        "dimension": "state_ownership", "affected_members": ["m1", "m2"],
        "alternatives": [
            {"description": "Promote values to shared instance state",
             "effect": "instance_state", "source_quote": "int no1 = 10; //local variable",
             "evidence_refs": ["member:MainApp.java::m1", "diagnostic:MainApp.java::m1::1",
                               "binding:MainApp.java::m1::no1", "member:MainApp.java::m1"]},
            {"description": "Pass values as parameters", "effect": "parameter_value",
             "source_quote": "void m1()", "evidence_refs": ["member:MainApp.java::m1",
                                                       "member:MainApp.java::m2"]},
        ],
        "question": "Should values be fields or parameters?",
    }
    return control, author


def _admit(root, control, author):
    return admit_gap(author=author, task_text=TASK, control=control,
                     scope=control["repair_scope"], repo_path=root)


def test_mainapp_spacing_mismatch_and_multiple_closed_refs(tmp_path):
    control, author = _case(tmp_path)
    gap = _admit(tmp_path, control, author)
    assert isinstance(gap, RepairIntentGap)
    assert gap.status == "waiting_for_clarification"
    assert gap.alternatives[0].source_quote == "int no1 = 10; //local variable"
    assert len(gap.anchors) == 4  # duplicate m1 refs share one anchor
    m1 = next(a for a in gap.anchors if a["ref"] == "member:MainApp.java::m1")
    assert "int no1 = 10;   //local variable\r\n" in m1["exact_text"]
    assert m1["repository_id"] == control["repair_scope"]["repository_id"]
    assert m1["source_fingerprint"] == sha256(SOURCE.encode()).hexdigest()
    assert SOURCE.encode()[m1["span"]["start_byte"]:m1["span"]["end_byte"]].decode() == m1["exact_text"]
    assert len(m1["anchor_id"]) == 64
    assert RepairIntentGap.from_dict(gap.as_dict()) == gap


@pytest.mark.parametrize("refs", [
    ["member:MainApp.java::helper"],
    ["member:Twosum.java::m1"],
    ["member:MainApp.java::m1", "member:MainApp.java::helper"],
    ["member:MainApp.java::m1::offset:456"],
    ["member:../../MainApp.java::m1"],
    ["diagnostic:MainApp.java::m1::9"],
])
def test_unknown_wrong_file_partial_and_arbitrary_refs_fail_closed(tmp_path, refs):
    control, author = _case(tmp_path)
    author["semantic_gap"]["alternatives"][0]["evidence_refs"] = refs
    with pytest.raises(EvidenceRefError, match="semantic_gap_evidence_unresolved"):
        _admit(tmp_path, control, author)


def test_ambiguous_member_and_stale_source_fail_closed(tmp_path):
    control, author = _case(tmp_path)
    duplicate = deepcopy(control)
    duplicate["repair_scope"]["members"].append(
        deepcopy(duplicate["repair_scope"]["members"][0]))
    with pytest.raises(EvidenceRefError):
        _admit(tmp_path, duplicate, author)
    (tmp_path / "MainApp.java").write_bytes(SOURCE.encode() + b"// changed\r\n")
    assert _admit(tmp_path, control, author) is None


def test_wrong_repository_control_and_anchor_tampering_fail_closed(tmp_path):
    control, author = _case(tmp_path)
    wrong_repo = deepcopy(control)
    wrong_repo["repair_scope"]["repository_id"] = "another-repository"
    assert _admit(tmp_path, wrong_repo, author) is None
    wrong_control = deepcopy(control)
    wrong_control["preflight_validation"]["control_sha256"] = "c" * 64
    assert _admit(tmp_path, wrong_control, author) is None
    gap = _admit(tmp_path, control, author)
    tampered = gap.as_dict()
    tampered["anchors"][0]["exact_text"] = "invented"
    with pytest.raises(ValueError, match="malformed_semantic_gap"):
        RepairIntentGap.from_dict(tampered)


def test_legacy_exact_quote_remains_exact(tmp_path):
    control, author = _case(tmp_path)
    for alternative in author["semantic_gap"]["alternatives"]:
        alternative.pop("evidence_refs")
    assert _admit(tmp_path, control, author) is None
    author["semantic_gap"]["alternatives"][0]["source_quote"] = "int no1 = 10;   //local variable"
    assert _admit(tmp_path, control, author) is not None


def test_web_handoff_persists_one_wait_with_authoritative_anchors(monkeypatch, tmp_path):
    from web import app as wa
    from web import session_store

    control, author = _case(tmp_path)
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(wa, "_patch_generation_harness_block", lambda *_: None)
    monkeypatch.setattr(wa, "build_control_prompt", lambda *_a, **_k: "AUTHOR PROMPT")
    calls = []
    monkeypatch.setattr(wa, "run_gemini_request", lambda prompt: calls.append(prompt)
                        or __import__("json").dumps(author))
    with wa.app.test_request_context("/generate_patch", method="POST",
                                     data={"repo_path": str(tmp_path)}):
        first = wa._generate_patch_from_control(str(tmp_path), control)
        second = wa._generate_patch_from_control(str(tmp_path), control)
    assert first["status"] == second["status"] == "waiting_for_clarification"
    assert first["clarification_session_id"] == second["clarification_session_id"]
    assert first["patch_candidate"] is None and first["write_authority"] is False
    assert len(session_store.load_sessions()) == 1
    assert len(first["repair_intent_gap"]["anchors"]) == 4
    assert "member:MainApp.java::m1" in calls[0]
    assert len(calls) == 2


def test_web_invalid_ref_is_typed_without_wait(monkeypatch, tmp_path):
    from web import app as wa
    from web import session_store

    control, author = _case(tmp_path)
    author["semantic_gap"]["alternatives"][0]["evidence_refs"] = ["member:Twosum.java::m1"]
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(wa, "_patch_generation_harness_block", lambda *_: None)
    monkeypatch.setattr(wa, "build_control_prompt", lambda *_a, **_k: "AUTHOR PROMPT")
    monkeypatch.setattr(wa, "run_gemini_request", lambda _: __import__("json").dumps(author))
    with wa.app.test_request_context("/generate_patch", method="POST",
                                     data={"repo_path": str(tmp_path)}):
        result = wa._generate_patch_from_control(str(tmp_path), control)
    assert result["code"] == "semantic_gap_evidence_unresolved"
    assert result["patch_candidate"] is None
    assert session_store.load_sessions() == []
