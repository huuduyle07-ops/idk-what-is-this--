"""Synthetic-only PATCH.SCOPE.EXPAND.1 replay; source stays in memory.

The frozen CONTINUE.1 complete answer is the sole answer fixture. No waiting
session, real BANK.2 answer, repository source file, or author is consumed.
"""
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

from core.class_semantic_context import project_class_semantic_context
from core.design_intent_continuation import compose_effective_design, continue_design_intent
from core.input_understanding import understand_request
from core.oop_intent_detector import detect_missing_future_design_contract
from core.oop_intent_session import bind_human_answer, make_stored_future_design_gap
from core.proposed_design_intent import project_proposed_design_intent
from core.repository_identity import derive_repository_id
from core.treesitter_parse import structural_definitions
from scripts.replay_oop_intent_continue1 import ANSWERS
from scripts.replay_oop_intent_detect2 import BANK, BANK2_TASK


def fixture_inputs(*, answer_name="complete", repository_root=None, source=None, task=None):
    """Compose the frozen semantic-ready chain without creating source files.

    Root identity is established by the frozen path-identity primitive. Source
    acquisition and all semantic projections use only the imported constants.
    """
    root = (Path(repository_root) if repository_root is not None
            else Path(__file__).resolve().parents[1])
    source = BANK if source is None else source
    task = BANK2_TASK if task is None else task
    repository_id = derive_repository_id(root)
    raw = source.encode("utf-8")
    source_fingerprint = hashlib.sha256(raw).hexdigest()
    target = next(item for item in structural_definitions(source, "java")["definitions"]
                  if item["kind"] == "class" and item["name"] == "BankAccount")
    context = project_class_semantic_context(
        raw=raw, language="java", file="bank.java", target=target,
        expected_source_fingerprint=source_fingerprint, repository_id=repository_id)
    contract = understand_request(task)
    design = project_proposed_design_intent(contract)
    first = detect_missing_future_design_contract(
        task_contract=contract, design_intent=design, current_context=context,
        current_source=raw, repository_id=repository_id)
    assert first.status == "clarification_required"
    gap = make_stored_future_design_gap(first, task_text=task, repo_path=str(root))
    assert gap is not None
    answer = bind_human_answer(gap, ANSWERS[answer_name]).as_dict()
    continuation = continue_design_intent(
        task_contract=contract, base_design=design, stored_gap=gap, stored_answer=answer,
        current_context=context, current_source=raw, repo_path=str(root))
    effective = compose_effective_design(design, continuation)
    detection = detect_missing_future_design_contract(
        task_contract=contract, design_intent=effective, current_context=context,
        current_source=raw, repository_id=repository_id, repo_path=str(root),
        stored_gap=gap, stored_answer=answer)
    expected = "no_gap" if answer_name == "complete" else "clarification_required"
    assert detection.status == expected
    return {
        "task_contract": contract, "base_design": design, "continuation": continuation,
        "design_intent": effective, "detection": detection, "current_context": context,
        "current_source": raw, "repository_id": repository_id, "repo_path": str(root),
        "stored_gap": gap, "stored_answer": answer,
    }


def _milliseconds(samples):
    return {"median_ms": round(statistics.median(samples) * 1000, 6),
            "max_ms": round(max(samples) * 1000, 6)}


def replay(*, repetitions=100):
    """Replay only the frozen complete continuation, ending at proposed scope."""
    from core.structural_scope_expansion import propose_structural_scope_expansion

    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    inputs = fixture_inputs()
    context = inputs["current_context"]
    base_before = inputs["base_design"].as_dict()
    context_before = context.as_dict()
    effective_before = inputs["design_intent"].as_dict()
    raw_before = inputs["current_source"]
    arguments = {
        "task_contract": inputs["task_contract"],
        "design_intent": inputs["design_intent"],
        "semantic_detection": inputs["detection"],
        "current_context": context,
        "current_source": inputs["current_source"],
        "repository_id": inputs["repository_id"],
        "current_scope": None,
    }
    timings, fingerprints = [], []

    def forbidden(*args, **kwargs):
        raise AssertionError("scope proposal attempted authoring, model, filesystem, traversal, or execution")

    # Resolve provider/author guard targets before forbidding file access. The
    # guarded phase then receives typed inputs and one already-acquired buffer.
    forbidden_targets = (
        "core.semantic_waiter_adapter.SemanticWaiterModelAdapter._complete",
        "core.control_engine.build_control_prompt",
        "core.control_engine.authoring_context_for_control_result",
        "core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "socket.create_connection", "socket.socket.connect",
        "subprocess.run", "subprocess.Popen", "os.system",
        "os.walk", "os.scandir", "os.listdir",
        "pathlib.Path.open", "pathlib.Path.read_bytes", "pathlib.Path.read_text",
        "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open",
    )
    with ExitStack() as guards:
        for target in forbidden_targets:
            guards.enter_context(patch(target, forbidden))
        for _ in range(repetitions):
            sample = {}
            result = propose_structural_scope_expansion(**arguments, timings=sample)
            assert result.status == "expansion_required", result
            assert result.proposal is not None
            assert result.candidate is None and result.patch == ""
            assert result.author_calls == result.model_calls == result.repository_traversals == 0
            assert not result.write_authority and not result.execution_authorized and not result.auto_apply
            assert result.first_remaining_blocker == "SCOPE_EXPANSION_REQUIRED"
            proposal = result.proposal
            assert not proposal.write_authority
            assert proposal.scope_authority == "proposal_only"
            fingerprints.append(proposal.fingerprint)
            timings.append(sample)
        assert len(set(fingerprints)) == 1
        assert inputs["base_design"].as_dict() == base_before
        assert inputs["design_intent"].as_dict() == effective_before
        assert context.as_dict() == context_before
        assert inputs["current_source"] == raw_before
        proposal_payload = proposal.as_dict()
        serialized_proposal_bytes = len(proposal.to_json().encode("utf-8"))

    timing_fields = (
        "semantic_ready_validation_seconds", "structural_comparison_seconds",
        "expansion_classification_seconds", "proposal_serialization_seconds", "total_seconds",
    )
    assert all(set(sample) == set(timing_fields) for sample in timings)
    return {
        "phase_id": "PATCH.SCOPE.EXPAND.1",
        "fixture_kind": "frozen_synthetic_complete_continuation_in_memory_only",
        "fixture_constants": {
            "source": "scripts.replay_oop_intent_detect2.BANK",
            "task": "scripts.replay_oop_intent_detect2.BANK2_TASK",
            "answer": "scripts.replay_oop_intent_continue1.ANSWERS[complete]",
        },
        "semantic_status": "ready", "semantic_detection_status": inputs["detection"].status,
        "scope_status": result.status,
        "first_remaining_blocker": result.first_remaining_blocker,
        "current_edit_scope": "none",
        "proposal": proposal_payload,
        "proposal_fingerprint": fingerprints[0],
        "serialized_proposal_bytes": serialized_proposal_bytes,
        "deterministic": True,
        "source": {
            "path": "bank.java", "bytes": len(raw_before),
            "fingerprint": hashlib.sha256(raw_before).hexdigest(),
            "class": context.class_identity.name,
            "fixture_note": ("Frozen replay source has private balance, a constructor(double opening), "
                             "unconditional void withdraw(double amount), and saving(double rate). "
                             "The conditional void withdraw measured-source case is a separate focused fixture."),
            "fields": [item.name for item in context.fields],
            "methods": [item.name for item in context.methods],
        },
        "performance": {
            "samples": repetitions, "provider_latency": "not_applicable",
            **{name: _milliseconds([sample[name] for sample in timings]) for name in timing_fields},
        },
        "authority": {
            "scope_authority": "proposal_only", "write_authority": False,
            "execution_authorized": False, "auto_apply": False, "repair_scope_authority": False,
        },
        "candidate": None, "patch": "",
        "author_calls": 0, "model_calls": 0, "repository_traversals": 0,
        "repair_scope_delta": 0, "authoring_scope_delta": 0,
        "source_bytes_unchanged": True, "current_context_unchanged": True,
        "base_design_unchanged": True, "effective_design_unchanged": True,
        "real_waiting_answer_consumed": False, "session_io": 0,
        "fixture_source_files_created": 0, "fixture_source_files_modified": 0,
        "forbidden_boundaries": list(forbidden_targets),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=100)
    options = parser.parse_args()
    report = replay(repetitions=options.repetitions)
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if options.output:
        options.output.write_text(serialized, encoding="utf-8")
    print(json.dumps({"semantic_status": report["semantic_status"],
                      "scope_status": report["scope_status"],
                      "first_remaining_blocker": report["first_remaining_blocker"],
                      "performance": report["performance"]}, indent=2))
