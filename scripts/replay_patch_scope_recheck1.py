"""Synthetic-only PATCH.SCOPE.RECHECK.1 replay with exact in-memory source.

No real BANK.2 session or answer is read. Guarded execution permits no source
I/O, repository traversal, provider/author call, execution or scope admission.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.oop_intent_session import bind_human_answer
from core.scope_semantic_recheck import (
    TIMING_FIELDS, compose_scope_transition_design, continue_scope_transition,
    make_stored_scope_transition_gap, recheck_scope_semantics,
)
from core.structural_scope_expansion import propose_structural_scope_expansion
from scripts.replay_patch_scope_expand1 import fixture_inputs


MEASURED_BANK = """class BankAccount {
  private String accountHolder;
  private double balance;
  BankAccount(String accountHolder, double balance) {
    this.accountHolder = accountHolder;
    this.balance = balance;
  }
  public void deposit(double amount) { balance += amount; }
  public void withdraw(double amount) {
    if (amount <= balance) { balance -= amount; }
  }
  public void saving(double interest, double year) {
    balance += balance * interest * year;
  }
  public void display() { System.out.println(accountHolder + balance); }
}"""
SAVING_DECLARATION = """  public void saving(double interest, double year) {
    balance += balance * interest * year;
  }
"""
ANSWERS = {
    "savings_only_on_subclass": (
        "Savings functionality should only belong to SavingAccount. "
        "BankAccount should no longer have savings behavior in the intended model."),
    "preserve_base_compatibility": (
        "Keep BankAccount's current saving behavior for compatibility, "
        "and SavingAccount should have separate savingBalance behavior."),
    "subclass_specialization": (
        "Keep a common savings operation concept, but SavingAccount should "
        "specialize it to use savingBalance."),
    "unknown": "Make it work somehow.",
    "conflicting": "Actually savingBalance should be on BankAccount.",
}


def _arguments(inputs):
    return {key: inputs[key] for key in (
        "task_contract", "design_intent", "current_context", "current_source", "repository_id")}


def _milliseconds(samples):
    return {"median_ms": round(statistics.median(samples) * 1000, 6),
            "max_ms": round(max(samples) * 1000, 6)}


def _assert_authority(value):
    assert value.scope_authority == "proposal_only"
    for key in ("write_authority", "execution_authorized", "auto_apply", "repair_scope_authority"):
        assert getattr(value, key) is False
    if hasattr(value, "candidate"):
        assert value.candidate is None and value.patch == ""


def replay(*, repetitions=100):
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    inputs = fixture_inputs(source=MEASURED_BANK)
    arguments = {**_arguments(inputs), "semantic_detection": inputs["detection"]}
    proposal_result = propose_structural_scope_expansion(**arguments)
    assert proposal_result.status == "expansion_required"
    proposal = proposal_result.proposal
    assert proposal is not None
    arguments.update(proposal=proposal, repo_path=inputs["repo_path"],
                     stored_gap=inputs["stored_gap"], stored_answer=inputs["stored_answer"])
    no_transition_inputs = fixture_inputs(source=MEASURED_BANK.replace(SAVING_DECLARATION, ""))
    no_transition_arguments = {**_arguments(no_transition_inputs),
                              "semantic_detection": no_transition_inputs["detection"]}
    no_transition_proposal = propose_structural_scope_expansion(**no_transition_arguments).proposal
    no_transition_arguments.update(proposal=no_transition_proposal,
        repo_path=no_transition_inputs["repo_path"], stored_gap=no_transition_inputs["stored_gap"],
        stored_answer=no_transition_inputs["stored_answer"])
    snapshot = {
        "base": inputs["base_design"].as_dict(), "effective": inputs["design_intent"].as_dict(),
        "continuation": inputs["continuation"].as_dict(), "context": inputs["current_context"].as_dict(),
        "source": inputs["current_source"], "proposal": proposal.as_dict(),
    }
    timing_samples, fingerprints = [], []
    answer_samples = {name: [] for name in ANSWERS}
    outcomes = {}

    def forbidden(*args, **kwargs):
        raise AssertionError("semantic recheck attempted provider, authoring, source I/O, traversal or execution")

    forbidden_targets = (
        "core.semantic_waiter_adapter.SemanticWaiterModelAdapter._complete",
        "core.control_engine.build_control_prompt",
        "core.control_engine.authoring_context_for_control_result",
        "core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "socket.create_connection", "socket.socket.connect", "subprocess.run", "subprocess.Popen",
        "os.system", "os.walk", "os.scandir", "os.listdir", "pathlib.Path.open",
        "pathlib.Path.read_bytes", "pathlib.Path.read_text", "pathlib.Path.write_bytes",
        "pathlib.Path.write_text", "builtins.open",
    )
    with ExitStack() as guards:
        # Resolving patch targets may import guard modules; all resolution is
        # completed before the source-I/O guards are installed.
        for target in forbidden_targets:
            guards.enter_context(patch(target, forbidden))
        for _ in range(repetitions):
            sample = {}
            result = recheck_scope_semantics(**arguments, timings=sample)
            assert result.status == "clarification_required" and result.gap is not None
            assert len(result.possible_intent_gaps) == 1
            _assert_authority(result)
            gap = make_stored_scope_transition_gap(result, task_contract=inputs["task_contract"],
                current_context=inputs["current_context"], repository_id=inputs["repository_id"])
            assert gap is not None and gap["gap_kind"] == "oop_intent"
            fingerprints.append(result.fingerprint)
            timing_samples.append(sample)
            for name, text in ANSWERS.items():
                answer = bind_human_answer(gap, text).as_dict()
                continuation_sample = {}
                continuation = continue_scope_transition(**arguments, stored_transition_gap=gap,
                    stored_transition_answer=answer, timings=continuation_sample)
                expected = ("answer_projection_bounded" if name == "unknown" else
                            "continuation_conflict" if name == "conflicting" else "clarification_projected")
                assert continuation.status == expected
                semantic_sample = {}
                checked = recheck_scope_semantics(**arguments, transition_continuation=continuation,
                    stored_transition_gap=gap, stored_transition_answer=answer, timings=semantic_sample)
                assert checked.status == ("no_gap" if expected == "clarification_projected" else expected)
                assert checked.scope_refresh_required == (expected == "clarification_projected")
                _assert_authority(continuation)
                _assert_authority(checked)
                answer_samples[name].append({"projection": continuation_sample, "recheck": semantic_sample})
                outcome = {"answer": text, "continuation": continuation.as_dict(),
                           "continuation_fingerprint": continuation.fingerprint,
                           "semantic_result": checked.as_dict(), "semantic_fingerprint": checked.fingerprint}
                if expected == "clarification_projected":
                    effective = compose_scope_transition_design(inputs["design_intent"], continuation)
                    _assert_authority(effective)
                    retry = continue_scope_transition(**arguments, stored_transition_gap=gap,
                        stored_transition_answer=answer, previous=continuation)
                    assert retry.fingerprint == continuation.fingerprint and retry.as_dict() == continuation.as_dict()
                    outcome.update(effective=effective.as_dict(), effective_fingerprint=effective.fingerprint,
                                   identical_retry_idempotent=True)
                if name in outcomes:
                    assert outcomes[name] == outcome
                outcomes[name] = outcome
        assert len(set(fingerprints)) == 1
        stale = recheck_scope_semantics(**{**arguments, "current_source": inputs["current_source"] + b"\n// changed"})
        assert stale.status == "reacquisition_required" and stale.gap is None
        forged = recheck_scope_semantics(**{**arguments, "proposal": replace(proposal, repository_id="forged_repository")})
        assert forged.status == "invalid_proposal" and forged.gap is None
        no_transition = recheck_scope_semantics(**no_transition_arguments)
        assert no_transition.status == "semantic_recheck_not_required" and no_transition.gap is None
        assert inputs["base_design"].as_dict() == snapshot["base"]
        assert inputs["design_intent"].as_dict() == snapshot["effective"]
        assert inputs["continuation"].as_dict() == snapshot["continuation"]
        assert inputs["current_context"].as_dict() == snapshot["context"]
        assert inputs["current_source"] == snapshot["source"] and proposal.as_dict() == snapshot["proposal"]

    assert all(set(sample) == set(TIMING_FIELDS) for sample in timing_samples)
    return {
        "phase_id": "PATCH.SCOPE.RECHECK.1", "fixture_kind": "synthetic_measured_source_in_memory_only",
        "original_answer_fixture": "scripts.replay_oop_intent_continue1.ANSWERS[complete]",
        "semantic_detection_status": inputs["detection"].status,
        "scope_status": proposal_result.status, "proposal_fingerprint": proposal.fingerprint,
        "effective_design_fingerprint": inputs["design_intent"].fingerprint,
        "recheck": result.as_dict(), "recheck_fingerprint": fingerprints[0], "stored_gap": gap,
        "waiting_state": "waiting_for_clarification", "first_remaining_blocker": "human_clarification_required",
        "answer_outcomes": outcomes,
        "negative_outcomes": {"stale_source": stale.status, "forged_proposal": forged.status,
                              "no_transition": no_transition.status},
        "source": {"path": "bank.java", "bytes": len(snapshot["source"]),
                   "fingerprint": hashlib.sha256(snapshot["source"]).hexdigest(),
                   "fixture_note": "In-memory measured shape: private base balance, holder/balance constructor, conditional void withdraw and saving(interest,year) mutating base balance."},
        "performance": {"samples": repetitions, "provider_latency": "not_applicable",
            "initial_recheck": {name: _milliseconds([sample[name] for sample in timing_samples]) for name in TIMING_FIELDS},
            "answers": {answer: {stage: {name: _milliseconds([sample[stage][name] for sample in samples])
                for name in TIMING_FIELDS} for stage in ("projection", "recheck")}
                for answer, samples in answer_samples.items()}},
        "deterministic": True, "source_bytes_unchanged": True, "current_context_unchanged": True,
        "prior_semantic_chain_unchanged": True, "proposal_unchanged": True,
        "authority": {"scope_authority": "proposal_only", "write_authority": False,
                      "execution_authorized": False, "auto_apply": False, "repair_scope_authority": False},
        "candidate": None, "patch": "", "repair_scope_delta": 0, "authoring_scope_delta": 0,
        "author_calls": 0, "model_calls": 0, "repository_traversals": 0,
        "real_waiting_answer_consumed": False, "session_io": 0,
        "fixture_source_files_created": 0, "fixture_source_files_modified": 0,
        "global_human_evidence_gap_created": False, "forbidden_boundaries": list(forbidden_targets),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=100)
    options = parser.parse_args()
    report = replay(repetitions=options.repetitions)
    if options.output:
        options.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"semantic_detection_status": report["semantic_detection_status"],
                      "scope_status": report["scope_status"], "waiting_state": report["waiting_state"],
                      "answer_outcomes": {key: value["continuation"]["status"]
                                          for key, value in report["answer_outcomes"].items()},
                      "performance": report["performance"]["initial_recheck"]}, indent=2))
