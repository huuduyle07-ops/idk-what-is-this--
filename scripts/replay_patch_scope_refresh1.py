"""Synthetic-only PATCH.SCOPE.REFRESH.1 replay; all Java stays in memory."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.oop_intent_session import bind_human_answer
from core.scope_semantic_recheck import (
    compose_scope_transition_design, continue_scope_transition,
    make_stored_scope_transition_gap, recheck_scope_semantics,
)
from core.structural_scope_expansion import propose_structural_scope_expansion
from core.structural_scope_refresh import refresh_structural_scope_proposal
from scripts.replay_patch_scope_expand1 import fixture_inputs

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
}
TIMING_FIELDS = ("parent_validation_seconds", "revised_semantic_validation_seconds",
                 "scope_regeneration_seconds", "semantic_diff_seconds",
                 "post_refresh_recheck_seconds", "total_seconds")


def _milliseconds(samples):
    return {"median_ms": round(statistics.median(samples) * 1000, 6),
            "max_ms": round(max(samples) * 1000, 6)}


def _scenario(inputs, answer_text):
    args = dict(task_contract=inputs["task_contract"], design_intent=inputs["design_intent"],
        semantic_detection=inputs["detection"], current_context=inputs["current_context"],
        current_source=inputs["current_source"], repository_id=inputs["repository_id"],
        current_scope=None)
    p0_result = propose_structural_scope_expansion(**args)
    assert p0_result.status == "expansion_required" and p0_result.proposal is not None
    p0 = p0_result.proposal
    recheck_args = dict(proposal=p0, **args, repo_path=inputs["repo_path"],
        stored_gap=inputs["stored_gap"], stored_answer=inputs["stored_answer"],
        expected_scope_fingerprint=None, related_contexts=())
    discovered = recheck_scope_semantics(**recheck_args)
    transition_gap = make_stored_scope_transition_gap(discovered,
        task_contract=inputs["task_contract"], current_context=inputs["current_context"],
        repository_id=inputs["repository_id"])
    assert transition_gap is not None
    answer = bind_human_answer(transition_gap, answer_text).as_dict()
    continuation = continue_scope_transition(**recheck_args,
        stored_transition_gap=transition_gap, stored_transition_answer=answer)
    effective = compose_scope_transition_design(inputs["design_intent"], continuation)
    receipt = recheck_scope_semantics(**recheck_args, transition_continuation=continuation,
        stored_transition_gap=transition_gap, stored_transition_answer=answer)
    refresh_inputs = dict(historical_proposal=p0, task_contract=inputs["task_contract"],
        original_design_intent=inputs["base_design"],
        continue1_continuation=inputs["continuation"],
        original_stored_gap=inputs["stored_gap"], original_stored_answer=inputs["stored_answer"],
        original_semantic_detection=inputs["detection"],
        transition_continuation=continuation, scope_transition_effective_design=effective,
        validated_recheck_receipt=receipt, stored_transition_gap=transition_gap,
        stored_transition_answer=answer, current_context=inputs["current_context"],
        current_source=inputs["current_source"], repository_id=inputs["repository_id"],
        repo_path=inputs["repo_path"], current_scope=None,
        expected_scope_fingerprint=None, related_contexts=())
    return p0, continuation, effective, receipt, refresh_inputs


def replay(*, repetitions=100):
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    inputs = fixture_inputs()
    raw_before = inputs["current_source"]
    context_before = inputs["current_context"].as_dict()
    design_before = inputs["design_intent"].as_dict()
    scenarios = {name: _scenario(inputs, text) for name, text in ANSWERS.items()}
    p0 = next(iter(scenarios.values()))[0]
    assert all(row[0].fingerprint == p0.fingerprint for row in scenarios.values())

    forbidden = ("socket.create_connection", "socket.socket.connect", "subprocess.run",
        "subprocess.Popen", "os.system", "os.walk", "os.scandir", "os.listdir",
        "pathlib.Path.open", "pathlib.Path.read_bytes", "pathlib.Path.read_text",
        "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open")
    outcomes, timings_by_case, fingerprints = {}, {}, {}

    def fail(*_args, **_kwargs):
        raise AssertionError("scope refresh attempted model, author, file I/O, traversal, or execution")

    with ExitStack() as guards:
        for target in forbidden:
            guards.enter_context(patch(target, fail))
        for name, (parent, continuation, effective, receipt, refresh_inputs) in scenarios.items():
            samples, proposal_rows = [], []
            for _ in range(repetitions):
                sample = {}
                refreshed = refresh_structural_scope_proposal(**refresh_inputs, timings=sample)
                assert refreshed.status == "refreshed" and refreshed.proposal is not None
                assert refreshed.structural_semantic_fixpoint is True
                assert refreshed.proposal.parent_proposal_fingerprint == parent.fingerprint
                assert refreshed.proposal.transition_continuation_fingerprint == continuation.fingerprint
                assert refreshed.proposal.effective_design_fingerprint == effective.fingerprint
                assert refreshed.post_refresh_recheck["status"] == "semantic_recheck_not_required"
                assert refreshed.candidate is None and refreshed.patch == ""
                assert refreshed.model_calls == refreshed.author_calls == refreshed.repository_traversals == 0
                assert not refreshed.write_authority and not refreshed.execution_authorized
                assert refreshed.repair_scope_delta == refreshed.authoring_scope_delta == 0
                samples.append(sample)
                proposal_rows.append(refreshed.proposal)
            assert len({item.fingerprint for item in proposal_rows}) == 1
            result = refresh_structural_scope_proposal(**refresh_inputs)
            proposal = result.proposal
            saving = next(item for item in proposal.existing_targets if item.target == "BankAccount::saving")
            transition_cap = next(item for item in proposal.required_capabilities
                                  if item.code == "existing_savings_transition")
            debit = next((item for item in proposal.existing_targets
                          if item.target == "BankAccount::successful_balance_debit_capability"), None)
            outcomes[name] = {
                "transition": continuation.typed_answer_commitments[0].value,
                "P1": proposal.as_dict(), "P1_fingerprint": proposal.fingerprint,
                "P0_fingerprint": parent.fingerprint,
                "effective_design_fingerprint": effective.fingerprint,
                "RECHECK_1": receipt.as_dict(),
                "post_refresh_recheck": result.post_refresh_recheck,
                "structural_semantic_fixpoint": result.structural_semantic_fixpoint,
                "semantic_diff": result.semantic_diff,
                "BankAccount_saving": {"category": saving.category, "reason": saving.reason,
                                        "transition_certainty": transition_cap.certainty},
                "base_debit": {"possible_API_change": debit is not None,
                    "target": None if debit is None else debit.target,
                    "certainty": next((x.certainty for x in proposal.required_capabilities
                        if x.code == "base_balance_debit"), None)},
                "performance": {field: _milliseconds([sample[field] for sample in samples])
                                for field in TIMING_FIELDS},
            }
            timings_by_case[name] = samples

    assert inputs["current_source"] == raw_before
    assert inputs["current_context"].as_dict() == context_before
    assert inputs["design_intent"].as_dict() == design_before
    assert p0.to_json() == scenarios["savings_only_on_subclass"][0].to_json()
    return {
        "phase_id": "PATCH.SCOPE.REFRESH.1",
        "fixture_kind": "synthetic_transition_answers_in_memory_only",
        "source": {"path": inputs["current_context"].file, "bytes": len(raw_before),
                   "fingerprint": hashlib.sha256(raw_before).hexdigest()},
        "historical_P0": p0.as_dict(), "historical_P0_fingerprint": p0.fingerprint,
        "scenarios": outcomes, "repetitions": repetitions,
        "authority": {"scope_authority": "proposal_only", "write_authority": False,
            "repair_scope_authority": False, "execution_authorized": False,
            "auto_apply": False, "apply_authority": False},
        "candidate": None, "patch": "", "repair_scope_delta": 0,
        "authoring_scope_delta": 0, "model_calls": 0, "author_calls": 0,
        "repository_traversals": 0, "real_BANK2_answer_consumed": False,
        "source_bytes_unchanged": True, "current_context_unchanged": True,
        "original_effective_design_unchanged": True,
        "P0_remains_historical": True, "P1_is_unadmitted": True,
        "performance": {name: {field: _milliseconds([sample[field] for sample in rows])
            for field in TIMING_FIELDS} for name, rows in timings_by_case.items()},
        "provider_latency": "not_applicable", "deterministic": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=100)
    options = parser.parse_args()
    report = replay(repetitions=options.repetitions)
    if options.output:
        options.output.write_text(json.dumps(report, ensure_ascii=False,
            sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"P0_fingerprint": report["historical_P0_fingerprint"],
        "P1_fingerprints": {key: value["P1_fingerprint"]
                            for key, value in report["scenarios"].items()},
        "transitions": {key: value["transition"] for key, value in report["scenarios"].items()},
        "performance": report["performance"]}, indent=2))
