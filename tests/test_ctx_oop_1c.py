"""CTX.OOP.1C fact/interpretation/gap and authority boundaries."""
from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError
from dataclasses import replace
import json
import time
from types import SimpleNamespace

import pytest

from core.class_semantic_context import project_class_semantic_context
from core.input_understanding import understand_request
from core.oop_semantic_review import (
    MAX_REVIEW_BYTES, OBSERVATION_KINDS, review_oop_semantics,
    render_oop_semantic_review,
)
from core.treesitter_parse import structural_definitions


BANK = """class BankAccount {
  private double balance;
  BankAccount(double opening) { this.balance = opening; }
  void deposit(double amount) { balance += amount; }
  void withdraw(double amount) { balance -= amount; }
  void saving(double rate) { balance += balance * rate; }
}"""
COUNTER = "class Counter { int value; void increment() { value++; } void reset() { value = 0; } }"


def review(source=BANK, task="Review BankAccount logic; is saving correct?", *,
           model_report=None, repair_owned=False, target_name=None):
    raw = source.encode()
    definitions = structural_definitions(source, "java")["definitions"]
    target = next(d for d in definitions if d["kind"] == "class" and
                  (target_name is None or d["name"] == target_name))
    context = project_class_semantic_context(
        raw=raw, language="java", file="bank.java", target=target,
        expected_source_fingerprint=hashlib.sha256(raw).hexdigest())
    result = review_oop_semantics(
        context=context, current_source=raw,
        task_contract=understand_request(task), model_report=model_report,
        repair_intent_owns_ambiguity=repair_owned)
    return result, context


def test_bankaccount_review_compiles_independent_of_candidate():
    result, _ = review()
    assert result.status == "clarification_required"
    assert result.authority == "read_only"
    assert any("balance is instance state" in f.description for f in result.structural_facts)
    shared = [f for f in result.structural_facts if f.kind == "same_state_mutation"]
    assert len(shared) == 1
    assert all(name in shared[0].description for name in ("deposit", "withdraw", "saving"))
    assert len([o for o in result.semantic_observations if o.kind == "domain_state_overlap"]) == 1
    assert result.possible_intent_gaps[0].owner == "human"
    assert {a.effect for a in result.possible_intent_gaps[0].alternatives} == {
        "shared_balance", "distinct_state"}
    assert "bug" not in result.to_json().casefold()
    assert "definite_bug" not in OBSERVATION_KINDS
    assert "Current behavior" in render_oop_semantic_review(result)
    assert "Why it may matter" in render_oop_semantic_review(result)
    assert len(result.to_json().encode()) <= MAX_REVIEW_BYTES
    with pytest.raises(FrozenInstanceError):
        result.authority = "write"


@pytest.mark.parametrize("task", [
    "This is just a simple exercise to practice compound interest using one balance. Review it.",
    "saving should apply compound interest directly to the account's current balance. Review it.",
])
def test_explicit_one_balance_and_pedagogy_suppress_gap(task):
    result, _ = review(task=task)
    assert result.status == "informational"
    assert not result.possible_intent_gaps
    assert any(o.kind == "domain_state_overlap" for o in result.semantic_observations)


def test_production_context_can_raise_gap_without_defect():
    result, _ = review(task="Review this production banking application account model.")
    assert result.status == "clarification_required"
    assert result.possible_intent_gaps[0].dimension == "domain_state_overlap"
    assert "defect" not in result.to_json().casefold()


def test_counter_same_state_is_only_informational():
    result, _ = review(COUNTER, "Review Counter behavior", target_name="Counter")
    assert result.status == "informational"
    assert any(f.kind == "same_state_mutation" for f in result.structural_facts)
    assert not result.possible_intent_gaps
    assert not any(o.kind == "domain_state_overlap" for o in result.semantic_observations)


def test_names_and_unrelated_patch_do_not_create_blocking_question():
    similar_names = """class Account {
      int ordinary; int savings;
      void saving() { savings++; }
      void deposit() { ordinary++; }
      void withdraw() { ordinary--; }
    }"""
    result, _ = review(similar_names, "Review Account", target_name="Account")
    assert not any(o.kind == "domain_state_overlap" for o in result.semantic_observations)
    assert not result.possible_intent_gaps
    unrelated, _ = review(task="Make saving public.")
    assert unrelated.status == "informational"
    assert not unrelated.possible_intent_gaps


def test_static_account_and_explicit_shared_counter():
    account = BANK.replace("private double balance", "private static double balance")
    result, _ = review(account, "Review realistic account behavior")
    assert any("class shares this state" in f.description for f in result.structural_facts)
    assert any(g.dimension == "state_ownership" for g in result.possible_intent_gaps)
    static_counter = COUNTER.replace("int value", "static int value")
    explicit, _ = review(static_counter,
        "Review Counter. All objects intentionally share one global counter.", target_name="Counter")
    assert not explicit.possible_intent_gaps
    static_constant = "class BankAccount { static final int LIMIT = 10; void inspect() {} }"
    constant, _ = review(static_constant, "Review realistic account behavior")
    assert not constant.possible_intent_gaps


def test_local_lifetime_and_constructor_initialization_are_exact_facts():
    source = """class Session {
      int total;
      Session(int opening) { this.total = opening; }
      void calculate() { int count = 0; count++; }
    }"""
    result, _ = review(source, "The count should persist across calls. Review it.", target_name="Session")
    assert any("count is method-local" in f.description for f in result.structural_facts)
    assert any("constructor assigns total" in f.description for f in result.structural_facts)
    assert any(o.kind == "lifecycle_semantics" for o in result.semantic_observations)
    assert not result.possible_intent_gaps  # The stated requirement already resolves intent.


def test_static_method_instance_relation_from_1a_only():
    source = "class A { int value; static void update(A a) { a.value++; } }"
    # 1A conservatively omits other-receiver field accesses; no relation may be invented.
    result, _ = review(source, "Review A", target_name="A")
    assert not any(o.kind == "static_instance_interaction" for o in result.semantic_observations)
    source = "class A { int value; static void update() { value++; } }"
    result, _ = review(source, "Review A", target_name="A")
    assert any(o.kind == "static_instance_interaction" for o in result.semantic_observations)


def test_unresolved_hierarchy_meaning_is_bounded():
    source = "class Child extends Parent { int value; void update() { value++; } }"
    result, _ = review(source, "Review dynamic dispatch and overrides", target_name="Child")
    assert result.status == "bounded"
    assert not result.semantic_observations and not result.possible_intent_gaps


def test_model_report_closed_refs_no_fact_or_gap_authority():
    baseline, context = review(task="Review this simple exercise using one balance")
    ref = next(r for r in baseline.evidence_refs if r.startswith("field:"))
    report = {"file": baseline.file, "class_identity": baseline.class_identity,
              "source_fingerprint": baseline.source_fingerprint,
              "observations": [{"kind": "domain_state_overlap", "evidence_refs": [ref],
        "description": "The domain may distinguish savings from ordinary balance.",
        "material_behavior_difference": True,
        "intent_question_optional": "Should it be separate?"}]}
    raw = BANK.encode()
    result = review_oop_semantics(context=context, current_source=raw,
        task_contract=understand_request("Review this simple exercise using one balance"),
        model_report=report)
    assert any(o.provenance == "model_interpretation" for o in result.semantic_observations)
    assert not result.possible_intent_gaps
    for bad in ("definite_bug", "state_ownership_typo"):
        with pytest.raises(ValueError):
            review(model_report={**report, "observations": [
                {**report["observations"][0], "kind": bad}]})
    with pytest.raises(ValueError):
        review(model_report={**report, "observations": [{**report["observations"][0],
               "evidence_refs": ["field:Other@0:1"]}]})
    for field, value in (("file", "other.java"), ("class_identity", "Other"),
                         ("source_fingerprint", "0" * 64)):
        with pytest.raises(ValueError):
            review(model_report={**report, field: value})


def test_stale_unsupported_comments_and_repair_intent_owner():
    result, context = review(BANK + " // saving should be separate")
    assert result.status == "clarification_required"  # Comment is not task intent.
    stale = review_oop_semantics(context=context, current_source=BANK.encode())
    assert stale.status == "stale" and not stale.semantic_observations
    unsupported = replace(context, language="python")
    assert review_oop_semantics(context=unsupported, current_source=(BANK + " // saving should be separate").encode()).status == "not_supported"
    owned, _ = review(repair_owned=True)
    assert owned.status == "informational" and not owned.possible_intent_gaps


def test_performance_and_serialization_bounds():
    start = time.perf_counter()
    for _ in range(20):
        result, _ = review()
    elapsed = (time.perf_counter() - start) / 20
    assert elapsed < 1.0
    assert result.normalization_seconds >= 0
    assert result.evidence_binding_seconds >= 0
    assert result.gap_admission_seconds >= 0
    assert json.loads(result.to_json())["authority"] == "read_only"


def test_existing_analysis_answer_call_receives_review_without_candidate(tmp_path):
    from core.analysis_evidence import AnalysisEvidence, AnalysisEvidenceItem
    from core.pipeline import _analysis_context_for_human, build_analysis_prompt_for_state
    (tmp_path / "bank.java").write_bytes(BANK.encode())
    evidence = AnalysisEvidence(items=(AnalysisEvidenceItem(
        path="bank.java", role="requested_path", text=BANK),))
    state = SimpleNamespace(
        analysis_evidence=evidence, live_route={"obligations": ()},
        user_input="Review BankAccount logic; is saving correct?",
        repo_path=str(tmp_path), memory_block="", history_block="", context_data="")
    prompt = build_analysis_prompt_for_state(state)
    assert "[READ-ONLY OOP SEMANTIC REVIEW]" in prompt
    assert "balance is instance state" in prompt
    assert "Should saving use this same balance" in prompt
    assert "proven defect" in prompt
    assert "[READ-ONLY OOP SEMANTIC REVIEW]" in prompt
    assert "[READ-ONLY OOP SEMANTIC REVIEW]" in _analysis_context_for_human(state)


def test_review_uses_existing_requested_path_selection(tmp_path):
    from core.analysis_evidence import collect_analysis_evidence
    from core.oop_semantic_review import review_acquired_java_evidence
    (tmp_path / "bank.java").write_bytes(BANK.encode())
    evidence = collect_analysis_evidence(str(tmp_path), requested_paths=["bank.java"])
    results = review_acquired_java_evidence(
        evidence=evidence, repository_root=str(tmp_path),
        task_contract=understand_request("Review bank.java: is saving correct?"))
    assert len(results) == 1
    assert results[0].status == "clarification_required"


def test_acquired_source_must_be_complete_and_exact(tmp_path):
    from core.analysis_evidence import AnalysisEvidence, AnalysisEvidenceItem
    from core.oop_semantic_review import review_acquired_java_evidence
    (tmp_path / "bank.java").write_bytes(BANK.encode())
    contract = understand_request("Review BankAccount logic")
    for text, truncated in ((BANK[:20], True), (BANK.replace("balance", "other"), False)):
        evidence = AnalysisEvidence(items=(AnalysisEvidenceItem(
            path="bank.java", role="requested_path", text=text, truncated=truncated),))
        assert not review_acquired_java_evidence(
            evidence=evidence, repository_root=str(tmp_path), task_contract=contract)
