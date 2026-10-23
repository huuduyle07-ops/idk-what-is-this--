"""Replay a declarative behavioral oracle from synthetic compile provider evidence.

This replay never invokes javac, Java, a test generator, a model or an author.
The compiler identity/result are explicit illustrative evidence, not a claim
that this phase measured compilation or behavior.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.behavioral_validation_specification import (
    FIRST_REMAINING_BLOCKER, PHASE_ID, TIMING_FIELDS,
    project_behavioral_validation_specification,
    validate_behavioral_validation_specification,
)
from core.structural_candidate_materialization import materialize_structural_candidate
from core.structural_compile_validation import (
    CompilerResult, JavacIdentity, normalize_structural_compile_result,
)
from scripts.replay_patch_candidate_materialize1 import (
    SCENARIOS, no_materialization_effects, synthetic_candidate_case,
)


@contextmanager
def no_specification_effects():
    """Reject providers, compiler execution, traversal, file access and mutation."""
    with no_materialization_effects(), ExitStack() as guards:
        for target in (
            "core.structural_compile_validation.compile_materialized_structural_candidate",
            "core.structural_compile_validation._run_javac",
            "web.preflight_request._start",
            "pathlib.Path.glob", "pathlib.Path.rglob", "pathlib.Path.iterdir",
        ):
            guards.enter_context(patch(target,
                side_effect=AssertionError("behavior-spec replay attempted a forbidden effect")))
        yield


def synthetic_compiled_case(name="preserve_base_compatibility"):
    """Reuse frozen synthetic construction and pure compile evidence normalization."""
    scope, fresh, candidate = synthetic_candidate_case(name)
    with no_specification_effects():
        materialized = materialize_structural_candidate(candidate, admitted_scope=scope, **fresh)
        compiler = JavacIdentity(str(Path("C:/trusted/javac.exe")), "a" * 64, "javac 23.0.2")
        receipt = normalize_structural_compile_result(materialized,
            compiler_result=CompilerResult(compiler=compiler, exit_code=0),
            candidate=candidate, admitted_scope=scope, **fresh)
    assert receipt.status == "compile_validated" and receipt.compile_success is True
    return scope, fresh, candidate, materialized, receipt


def _negative_result(operation, expected_status):
    try:
        result = operation()
    except ValueError as exc:
        status = getattr(exc, "code", str(exc))
        assert status == expected_status, (status, expected_status)
        return {"status": status, "specification_available": False}
    payload = result.as_dict()
    assert not payload.get("obligations"), "failed gate emitted obligations"
    assert result.status == expected_status, (result.status, expected_status)
    return {"status": result.status, "specification_available": False}


def replay(*, repetitions=5):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    fixtures = {name: synthetic_compiled_case(name) for name in SCENARIOS}
    scenarios = {}
    with no_specification_effects():
        for name, (scope, fresh, candidate, materialized, receipt) in fixtures.items():
            before = (scope.to_json(), candidate.to_json(), materialized.to_json(),
                      receipt.to_json(), fresh["plan"].to_json(), fresh["current_source"])
            samples, fingerprints = [], []
            for _ in range(repetitions):
                timings = {}
                spec = project_behavioral_validation_specification(receipt,
                    materialized=materialized, candidate=candidate, admitted_scope=scope,
                    timings=timings, **fresh)
                assert validate_behavioral_validation_specification(spec.as_dict(),
                    compile_receipt=receipt, materialized=materialized, candidate=candidate,
                    admitted_scope=scope, **fresh) == spec
                assert set(timings) == set(TIMING_FIELDS)
                samples.append(timings)
                fingerprints.append(spec.fingerprint)
            assert len(set(fingerprints)) == 1
            assert before == (scope.to_json(), candidate.to_json(), materialized.to_json(),
                              receipt.to_json(), fresh["plan"].to_json(), fresh["current_source"])
            scenarios[name] = {
                "behavioral_specification": spec.as_dict(),
                "compile_receipt_fingerprint": receipt.fingerprint,
                "compile_receipt_kind": "synthetic_provider_evidence_only",
                "deterministic": True, "source_bytes_unchanged": True,
                "candidate_unchanged": True, "materialization_unchanged": True,
                "historical_plan_unchanged": True,
                "performance": {key: {
                    "median_ms": round(statistics.median(s[key] for s in samples) * 1000, 6),
                    "max_ms": round(max(s[key] for s in samples) * 1000, 6),
                } for key in TIMING_FIELDS},
            }

        scope, fresh, candidate, materialized, receipt = fixtures["preserve_base_compatibility"]
        spec = project_behavioral_validation_specification(receipt,
            materialized=materialized, candidate=candidate, admitted_scope=scope, **fresh)
        negatives = {}
        for field, value in (("test_code", "forbidden executable payload"),
                             ("command", "forbidden command payload"),
                             ("test_write_authority", True), ("execution_authorized", True),
                             ("write_authority", True), ("apply_authority", True)):
            payload = deepcopy(spec.as_dict())
            payload[field] = value
            negatives["forbidden_" + field] = _negative_result(lambda payload=payload:
                validate_behavioral_validation_specification(payload, compile_receipt=receipt,
                    materialized=materialized, candidate=candidate, admitted_scope=scope, **fresh),
                "behavior_spec_invalid" if field in {"test_code", "command"}
                else "behavior_spec_authority_escalation")

        stale = receipt.as_dict()
        stale["materialization_fingerprint"] = "b" * 64
        negatives["stale_compile_receipt"] = _negative_result(lambda:
            project_behavioral_validation_specification(stale,
                materialized=materialized, candidate=candidate, admitted_scope=scope, **fresh),
            "behavior_spec_stale")
        other_scope, other_fresh, other_candidate, other_materialized, _ = fixtures["savings_only_on_subclass"]
        negatives["wrong_transition_lineage"] = _negative_result(lambda:
            project_behavioral_validation_specification(receipt, materialized=other_materialized,
                candidate=other_candidate, admitted_scope=other_scope, **other_fresh),
            "behavior_spec_stale")
        failed_receipt = normalize_structural_compile_result(materialized,
            compiler_result=CompilerResult(compiler=receipt.compiler_result.compiler, exit_code=1),
            candidate=candidate, admitted_scope=scope, **fresh)
        negatives["compile_failed"] = _negative_result(lambda:
            project_behavioral_validation_specification(failed_receipt,
                materialized=materialized, candidate=candidate, admitted_scope=scope, **fresh),
            "behavior_spec_unavailable_due_compile_failure")

    return {
        "phase_id": PHASE_ID,
        "fixture_kind": "synthetic_frozen_semantic_candidate_lineage_and_compile_provider_evidence",
        "frozen_BANK_scenario": "preserve_base_compatibility",
        "scenarios": scenarios, "negative_cases": negatives, "repetitions": repetitions,
        "actual_javac_invocation_count": 0, "actual_version_probe_count": 0,
        "java_execution_count": 0, "arbitrary_command_execution_count": 0,
        "test_generation_count": 0, "test_generated": False,
        "model_calls": 0, "author_calls": 0, "repository_traversals": 0,
        "source_mutation": False, "virtual_source_repair": False,
        "real_BANK2_approval_consumed": False, "MainApp_session_touched": False,
        "behavior_validated": False, "correctness_proven": False,
        "authority": "behavioral_oracle_only", "test_write_authority": False,
        "execution_authorized": False, "write_authority": False, "apply_authority": False,
        "first_remaining_blocker": FIRST_REMAINING_BLOCKER,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    result = replay(repetitions=options.repetitions)
    if options.output:
        options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8", newline="\n")
    print(json.dumps({
        "phase_id": result["phase_id"],
        "scenarios": {name: {
            "status": row["behavioral_specification"]["status"],
            "obligation_count": len(row["behavioral_specification"]["obligations"]),
            "performance": row["performance"],
        } for name, row in result["scenarios"].items()},
        "negative_cases": result["negative_cases"],
        "actual_javac_invocation_count": result["actual_javac_invocation_count"],
        "java_execution_count": result["java_execution_count"],
        "first_remaining_blocker": result["first_remaining_blocker"],
    }, indent=2))
