"""REPAIR.INTENT.DETECT.1 compiler and syntax grounded admission tests."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import re
import shutil

from core.repair_intent import RepairIntentGap
from core.repair_intent_ambiguity import detect_repair_intent_ambiguity
from core.repair_scope import build_repair_scope
from core.repository_identity import derive_repository_id
import pytest


TASK = "Check Demo.java and fix its compile errors"
SOURCE = ("class Demo {\r\n"
          "  int value = 1;\r\n"
          "  void left() { int a = 2; System.out.println(b); }\r\n"
          "  void right() { int b = 3; System.out.println(a); }\r\n"
          "  static void third() { System.out.println(value + a + b); }\r\n"
          "}\r\n")


def _diagnostic(source: str, line_text: str, name: str, *, occurrence: int = 1,
                message: str = "cannot find symbol") -> dict:
    line = next(number for number, row in enumerate(source.splitlines(), 1)
                if line_text in row)
    row = source.splitlines()[line - 1]
    indexes = [match.start() for match in re.finditer(
        r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", row)]
    return {"kind": "compiler_error", "language": "java", "file": "Demo.java",
            "line": line, "col": indexes[occurrence - 1] + 1,
            "severity": "error", "message": message}


def _case(tmp_path, source: str = SOURCE, diagnostics: list[dict] | None = None,
          primary: str = "left"):
    (tmp_path / "Demo.java").write_bytes(source.encode())
    if diagnostics is None:
        diagnostics = [
            _diagnostic(source, "void left", "b", occurrence=1),
            _diagnostic(source, "void right", "a", occurrence=1),
            _diagnostic(source, "void third", "value", message=(
                "non-static variable value cannot be referenced from a static context")),
            _diagnostic(source, "void third", "a", occurrence=1),
            _diagnostic(source, "void third", "b", occurrence=1),
        ]
    repo_id = derive_repository_id(tmp_path)
    source_hash = sha256((tmp_path / "Demo.java").read_bytes()).hexdigest()
    preflight = {
        "ran": True, "ok": False, "category": "build_error",
        "evidence_source": "PREFLIGHT.REQUEST.1", "evidence_kind": "compile_evidence",
        "measured": True, "receipt_fingerprint": "b" * 64,
        "control_sha256": "a" * 64, "repository_id": repo_id,
        "source_fingerprints": [{"path": "Demo.java", "sha256": source_hash}],
        "locations": diagnostics,
        "targets": [{"path": "Demo.java", "errors": len(diagnostics), "warnings": 0}],
    }
    scope = build_repair_scope(
        repo_path=tmp_path, primary_file="Demo.java", primary_symbol=primary,
        primary_kind="function", language="java", preflight=preflight,
        receipt_control_fingerprint="a" * 64).as_dict()
    assert scope["status"] == "complete"
    return {"query": TASK, "repair_scope": scope, "preflight_validation": preflight}


def _detect(tmp_path, control, task=TASK, language="java"):
    return detect_repair_intent_ambiguity(
        task_text=task, control=control, repo_path=tmp_path, language=language)


def test_combined_facts_one_grounded_wait_without_author(tmp_path):
    control = _case(tmp_path)
    result = _detect(tmp_path, control)
    assert result.gap is not None
    assert len(result.facts) == 3
    assert {fact.ambiguity_kind for fact in result.facts} == {
        "cross_member_local_reference", "static_instance_state_ambiguity"}
    assert result.gap.dimension == "state_ownership"
    assert result.gap.affected_members == ("left", "right", "third")
    assert len(result.gap.anchors) == 8
    assert {anchor["kind"] for anchor in result.gap.anchors} == {"diagnostic", "member"}
    assert all(anchor["source_fingerprint"] == control["repair_scope"]["source_fingerprint"]
               for anchor in result.gap.anchors)
    assert RepairIntentGap.from_dict(result.gap.as_dict()) == result.gap
    assert result.as_dict()["model_calls"] == result.as_dict()["network_calls"] == 0

@pytest.mark.skipif(shutil.which("javac") is None, reason="javac unavailable")
def test_fresh_bootstrap_projects_scope_before_detector(tmp_path, monkeypatch):
    """A fresh CONTROL has no RepairScope until existing prompt preparation."""
    from web.control_bootstrap import FreshControlBootstrapRequest, bootstrap_fresh_control
    from web.preflight_request import preflight_bootstrapped_control
    from web import app as wa, session_store

    (tmp_path / "Demo.java").write_bytes(SOURCE.encode())
    bootstrap = bootstrap_fresh_control(
        FreshControlBootstrapRequest(TASK, str(tmp_path)),
        provider=lambda *_a, **_k: __import__("json").dumps({
            "hypotheses": [{"symbol": "Demo.java::left",
                            "likely_issue": "unresolved Java value",
                            "reasons": ["compiler evidence needed"]}],
            "evidence_gaps": [{"need": "compile_evidence",
                               "detail": "compile current Java source",
                               "targets": ["Demo.java"]}],
        }),
    )
    assert bootstrap.bootstrapped
    preflight = preflight_bootstrapped_control(bootstrap)
    assert preflight.status == "evidence_measured"
    assert "repair_scope" not in preflight.control
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(wa, "_patch_generation_harness_block", lambda *_: None)
    monkeypatch.setattr(wa, "run_gemini_request", lambda *_: (_ for _ in ()).throw(
        AssertionError("patch author called")))
    with wa.app.test_request_context("/generate_patch", method="POST",
                                     data={"repo_path": str(tmp_path)}):
        result = wa._generate_patch_from_control(str(tmp_path), preflight.control)
        repeated = wa._generate_patch_from_control(str(tmp_path), preflight.control)
    assert result["status"] == "waiting_for_clarification"
    assert result["clarification_session_id"] == repeated["clarification_session_id"]
    assert len(result["ambiguity_detection"]["facts"]) == 3
    assert len(session_store.load_sessions()) == 1
    assert result["patch_candidate"] is None and result["write_authority"] is False


def test_unresolved_typo_and_unrelated_member_do_not_trigger(tmp_path):
    source = SOURCE.replace("println(b);", "println(unknown);", 1)
    diagnostic = _diagnostic(source, "void left", "unknown")
    control = _case(tmp_path, source, [diagnostic])
    assert _detect(tmp_path, control).gap is None


def test_comment_or_string_spelling_is_not_a_declaration(tmp_path):
    source = SOURCE.replace("int b = 3;", 'int c = 3; String note = "b"; // b')
    control = _case(tmp_path, source, [_diagnostic(source, "void left", "b")])
    assert _detect(tmp_path, control).gap is None


def test_repeated_diagnostic_deduplicates_fact(tmp_path):
    diagnostic = _diagnostic(SOURCE, "void left", "b")
    control = _case(tmp_path, SOURCE, [diagnostic, deepcopy(diagnostic),
                                      _diagnostic(SOURCE, "void right", "a")])
    result = _detect(tmp_path, control)
    assert len(result.facts) == 2
    assert result.gap is not None
    assert len(next(fact for fact in result.facts
                    if fact.declaration.name == "b").diagnostic_refs) == 2


def test_existing_field_blocks_cross_local_claim(tmp_path):
    source = SOURCE.replace("  int value = 1;", "  int value = 1; int a = 4;")
    control = _case(tmp_path, source, [_diagnostic(source, "void right", "a")],
                    primary="right")
    assert _detect(tmp_path, control).gap is None


def test_comment_string_wrong_file_stale_and_unsupported_language(tmp_path):
    control = _case(tmp_path)
    assert _detect(tmp_path, control, language="python").gap is None
    wrong = deepcopy(control)
    wrong["preflight_validation"]["locations"][0]["file"] = "Other.java"
    assert _detect(tmp_path, wrong).gap is None
    (tmp_path / "Demo.java").write_bytes(SOURCE.encode() + b"// changed\n")
    assert _detect(tmp_path, control).gap is None


def test_explicit_commitment_suppresses_only_resolved_dimension(tmp_path):
    control = _case(tmp_path)
    static_intent = _detect(tmp_path, control,
                            "Keep third static and make it use the shared static state.")
    assert static_intent.gap is not None
    assert {fact.ambiguity_kind for fact in static_intent.facts} == {
        "cross_member_local_reference"}
    all_intent = _detect(tmp_path, control,
                         "Keep a and b method-local and pass values. "
                         "Keep third static and make it use the shared static state.")
    assert all_intent.gap is None
    assert all_intent.facts == ()
