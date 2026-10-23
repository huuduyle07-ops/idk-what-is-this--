"""Synthetic APPROVE.1 dogfood: buffers only, no real answer or approval."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jinja2 import Environment
from core.structural_scope_approval import (
    DECISIONS, TIMING_FIELDS, HumanScopeDecisionAction, prepare_structural_scope_review,
    decide_structural_scope_ceiling, validate_structural_scope_approval_receipt,
)
from core.structural_scope_refresh import refresh_structural_scope_proposal
from scripts.replay_patch_scope_expand1 import fixture_inputs
from scripts.replay_patch_scope_refresh1 import _scenario, ANSWERS


def replay(*, repetitions=10):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    inputs = fixture_inputs()
    source_before = inputs["current_source"]
    template = Environment(autoescape=True).from_string((Path(__file__).resolve().parents[1] /
        "web/templates/scope_approval_review.html").read_text(encoding="utf-8"))
    scenarios = {}
    for transition, text in ANSWERS.items():
        *_, refresh_inputs = _scenario(inputs, text)
        refreshed = refresh_structural_scope_proposal(**refresh_inputs)
        scenarios[transition] = dict(proposal=refreshed.proposal, refresh_result=refreshed, **refresh_inputs)
    targets = ("core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "core.control_engine.build_control_prompt", "core.control_engine.authoring_context_for_control_result",
        "socket.create_connection", "socket.socket.connect", "subprocess.run", "subprocess.Popen",
        "os.system", "os.walk", "os.scandir", "os.listdir", "pathlib.Path.open", "pathlib.Path.read_bytes",
        "pathlib.Path.read_text", "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open")
    results = {}
    def forbidden(*_a, **_kw):
        raise AssertionError("approval attempted author/model/file I/O/traversal/execution")
    with ExitStack() as guards:
        for target in targets:
            guards.enter_context(patch(target, forbidden))
        for transition, arguments in scenarios.items():
            review = prepare_structural_scope_review(**arguments)
            summary_html = template.render(scope_approval={"summary": review.presentation,
                "status": "scope_proposal_awaiting_approval", "proposal_fingerprint": review.proposal.fingerprint,
                "decision_available": False})
            decisions = {}
            for decision in DECISIONS:
                note = "Synthetic revision note; no reinterpretation." if decision == "request_scope_revision" else ""
                action = HumanScopeDecisionAction(decision, review.proposal.fingerprint, review.fingerprint,
                                                 "explicit_human", "synthetic_human_action", note)
                samples, receipts = [], []
                for _ in range(repetitions):
                    timings = {}
                    started = perf_counter()
                    receipt = decide_structural_scope_ceiling(**arguments, human_action=action, timings=timings)
                    checked = validate_structural_scope_approval_receipt(receipt, stored_human_action=action,
                        require_eligible=False, timings=timings, **arguments)
                    timings["total_seconds"] = perf_counter() - started
                    assert checked == receipt
                    assert receipt.eligible_for_admission is (decision == "approve_exact_scope_ceiling")
                    assert receipt.repair_scope_delta == receipt.authoring_scope_delta == 0
                    assert receipt.candidate is None and receipt.patch == ""
                    assert not any((receipt.write_authority, receipt.execution_authorized,
                                    receipt.auto_apply, receipt.apply_authority, receipt.repair_scope_authority))
                    assert receipt.model_calls == receipt.author_calls == receipt.repository_traversals == 0
                    samples.append(timings)
                    receipts.append(receipt.fingerprint)
                assert len(set(receipts)) == 1
                assert decide_structural_scope_ceiling(**arguments, human_action=action,
                    previous_receipt=receipt).fingerprint == receipt.fingerprint
                decisions[decision] = {"receipt": receipt.as_dict(), "receipt_fingerprint": receipt.fingerprint,
                    "performance": {name: {"median_ms": round(statistics.median(x[name] for x in samples)*1000, 6),
                        "max_ms": round(max(x[name] for x in samples)*1000, 6)} for name in TIMING_FIELDS},
                    "idempotent": True, "scope_admission_occurred": False}
            results[transition] = {"P1_fingerprint": review.proposal.fingerprint,
                "review_fingerprint": review.fingerprint, "summary": review.presentation,
                "rendered_summary_html": summary_html, "decisions": decisions,
                "structural_semantic_fixpoint": True, "P1_authority": review.proposal.scope_authority}
    assert inputs["current_source"] == source_before
    return {"phase_id": "PATCH.SCOPE.APPROVE.1", "schema_version": "patch_scope_approve_1_replay_v1",
        "fixture_kind": "synthetic_human_actions_and_semantic_answers_in_memory_only",
        "scenarios": results, "repetitions": repetitions,
        "source_fingerprint": sha256(source_before).hexdigest(), "source_bytes_unchanged": True,
        "real_BANK2_answer_consumed": False, "real_approval_consumed": False,
        "repair_scope_delta": 0, "authoring_scope_delta": 0, "candidate": None, "patch": "",
        "write_authority": False, "execution_authorized": False, "auto_apply": False, "apply_authority": False,
        "model_calls": 0, "author_calls": 0, "repository_traversals": 0,
        "provider_latency": "not_applicable", "deterministic": True,
        "first_remaining_blocker": "SCOPE_ADMISSION_NOT_IMPLEMENTED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=10)
    options = parser.parse_args()
    result = replay(repetitions=options.repetitions)
    if options.output:
        options.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding="utf-8")
    print(json.dumps({"phase_id": result["phase_id"], "repetitions": result["repetitions"],
        "scenarios": {name: {"P1_fingerprint": row["P1_fingerprint"], "decisions": {
            decision: {"receipt_fingerprint": data["receipt_fingerprint"], "performance": data["performance"]}
            for decision, data in row["decisions"].items()}} for name, row in result["scenarios"].items()},
        "first_remaining_blocker": result["first_remaining_blocker"]}, indent=2))
