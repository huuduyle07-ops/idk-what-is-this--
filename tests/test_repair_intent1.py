"""REPAIR.INTENT.1 deterministic admission, binding and continuation tests."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from core.repair_intent import (
    ClarificationAnswer, RepairIntentGap, admit_gap, bind_answer,
    render_human_clarification, render_question, validate_resume,
)
from core.repository_identity import derive_repository_id


TASK = "Help me check if the code in MainApp.java is ok, then fix it"
SOURCE = """class MainApp {
  int no = 130;
  static int sno = 230;
  void m1() { int no1 = 10; System.out.println(no1 + no2); }
  void m2() { int no2 = 20; System.out.println(no1 + no2); }
  static void m3() { System.out.println(no); }
}
"""


def _evidence(root: Path):
    (root / "MainApp.java").write_text(SOURCE, encoding="utf-8")
    repo_id = derive_repository_id(root)
    source_hash = sha256((root / "MainApp.java").read_bytes()).hexdigest()
    control_hash = "a" * 64
    receipt_hash = "b" * 64
    scope = {
        "status": "complete", "primary_target": {"file": "MainApp.java", "symbol": "m1"},
        "members": [{"symbol": x} for x in ("m1", "m2", "m3")],
        "repository_id": repo_id, "source_fingerprint": source_hash,
        "control_fingerprint": control_hash, "evidence_fingerprint": receipt_hash,
    }
    control = {"query": TASK, "repair_scope": scope,
               "preflight_validation": {"repository_id": repo_id,
                                        "control_sha256": control_hash,
                                        "receipt_fingerprint": receipt_hash}}
    author = {"patch_candidate": None, "needs_escalation": True,
              "escalation_reason": "semantic_intent_required", "semantic_gap": {
                  "dimension": "state_ownership", "affected_members": ["m3"],
                  "alternatives": [
                      {"description": "Use per-instance state", "effect": "instance_state",
                       "source_quote": "int no = 130"},
                      {"description": "Use shared static state", "effect": "shared_state",
                       "source_quote": "static int sno = 230"}],
                  "question": "Should m3 use per-instance state or shared static state?"}}
    return control, author


def _gap(root: Path):
    control, author = _evidence(root)
    gap = admit_gap(author=author, task_text=TASK, control=control,
                    scope=control["repair_scope"], repo_path=root)
    assert isinstance(gap, RepairIntentGap)
    return gap, control, author


def test_mainapp_ambiguity_waits_without_patch_or_authority(tmp_path):
    gap, control, author = _gap(tmp_path)
    assert gap.status == "waiting_for_clarification"
    assert author["patch_candidate"] is None
    assert "per-instance" in render_question(gap)
    assert "shared static" in render_question(gap)
    assert "another intended behavior" in render_question(gap)
    assert gap.affected_members == ("m3",)
    assert RepairIntentGap.from_dict(json.loads(json.dumps(gap.as_dict()))) == gap


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(escalation_reason="structural_blocker"),
    lambda x: x.update(patch_candidate={"patched_snippet": "guess"}),
    lambda x: x["semantic_gap"].update(alternatives=x["semantic_gap"]["alternatives"][:1]),
    lambda x: x["semantic_gap"]["alternatives"][1].update(effect="instance_state"),
    lambda x: x["semantic_gap"]["alternatives"][1].update(source_quote="absent source"),
    lambda x: x["semantic_gap"].update(affected_members=["outside_scope"]),
])
def test_no_grounded_divergence_means_no_gap(tmp_path, mutation):
    control, author = _evidence(tmp_path)
    mutation(author)
    assert admit_gap(author=author, task_text=TASK, control=control,
                     scope=control["repair_scope"], repo_path=tmp_path) is None


def test_authoritative_choice_prevents_wait(tmp_path):
    control, author = _evidence(tmp_path)
    assert admit_gap(author=author, task_text=TASK, control=control,
                     scope=control["repair_scope"], repo_path=tmp_path,
                     authoritative_choice="Use the static value") is None


def test_human_answer_is_free_text_and_bound_to_same_evidence(tmp_path):
    gap, control, _ = _gap(tmp_path)
    answer = bind_answer(gap, "Neither. m3 should use the same object as main.")
    assert answer.provenance == "human_provided_semantic_evidence"
    assert bind_answer(gap, answer.text, answer) is answer
    with pytest.raises(ValueError, match="clarification_conflict"):
        bind_answer(gap, "Use shared state", answer)
    assert validate_resume(gap, answer, task_text=TASK, control=control,
                           repo_path=tmp_path) == "current"
    assert answer.text in render_human_clarification(answer)
    assert "[HUMAN CLARIFICATION]" in render_human_clarification(answer)


def test_stale_wrong_repo_control_and_task_refused(tmp_path):
    repo = tmp_path / "one"
    repo.mkdir()
    gap, control, _ = _gap(repo)
    answer = bind_answer(gap, "Use shared static state")
    assert validate_resume(gap, answer, task_text="another task", control=control,
                           repo_path=repo) == "wrong_task"
    other = tmp_path / "two"
    other.mkdir()
    assert validate_resume(gap, answer, task_text=TASK, control=control,
                           repo_path=other) == "wrong_repository"
    wrong_control = deepcopy(control)
    wrong_control["preflight_validation"]["control_sha256"] = "c" * 64
    assert validate_resume(gap, answer, task_text=TASK, control=wrong_control,
                           repo_path=repo) == "wrong_control"
    (repo / "MainApp.java").write_text(SOURCE + "// changed\n", encoding="utf-8")
    assert validate_resume(gap, answer, task_text=TASK, control=control,
                           repo_path=repo) == "stale_source"


def test_malformed_gap_and_answer_rejected(tmp_path):
    gap, _, _ = _gap(tmp_path)
    malformed = gap.as_dict()
    malformed["alternatives"] = malformed["alternatives"][:1]
    with pytest.raises(ValueError):
        RepairIntentGap.from_dict(malformed)
    with pytest.raises(ValueError):
        ClarificationAnswer(gap.ambiguity_id, "")
