"""Replay pure bounded scenario admission using frozen illustrative evidence.

The frozen evidence adapter permits compile evidence only. Capability-ready
scenarios are reported separately from execution admission; this replay never
supplies an invented runtime authority grant or performs a runtime effect.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import behavioral_execution_admission as owner
from scripts.replay_patch_candidate_behavior_exec_plan1 import (
    build as build_plan, direct_only_planning_fixture,
    no_execution_planning_effects, planning_fixture,
)
from scripts.replay_patch_candidate_materialize1 import SCENARIOS


@contextmanager
def no_admission_effects():
    """Reject execution, source rendering and issuance of actual-read receipts."""
    with no_execution_planning_effects(), patch(
            "core.read_only_reflection_java.render_read_only_reflection_adapter",
            side_effect=AssertionError("admission attempted reflection source generation")), patch(
            "core.read_only_reflection._issue_adapter_observation",
            side_effect=AssertionError("admission attempted an actual-read receipt")):
        yield


def lineage(fixture, **changes):
    scope, fresh, candidate, materialized, receipt, specification = fixture
    return {
        "specification": specification, "compile_receipt": receipt,
        "materialized": materialized, "candidate": candidate,
        "admitted_scope": scope, **fresh, **changes,
    }


def build(fixture, execution_plan=None, **changes):
    if execution_plan is None:
        execution_plan = build_plan(fixture)
    return owner.build_behavioral_execution_admission(execution_plan,
        **lineage(fixture, **changes))


def validate(admission, fixture, execution_plan=None, **changes):
    if execution_plan is None:
        execution_plan = build_plan(fixture)
    return owner.validate_behavioral_execution_admission(admission,
        execution_plan=execution_plan, **lineage(fixture, **changes))


def _negative(operation, expected):
    try:
        operation()
    except ValueError as exc:
        code = getattr(exc, "code", str(exc))
        assert code in expected, (code, expected)
        return {"status": code, "admission_accepted": False}
    raise AssertionError("negative behavioral admission was accepted")


def _snapshot(fixture, plan):
    scope, fresh, candidate, materialized, receipt, specification = fixture
    return (scope.to_json(), fresh["plan"].to_json(), candidate.to_json(),
        materialized.to_json(), receipt.to_json(), specification.to_json(),
        fresh["current_source"], plan.to_json())


def replay(*, repetitions=5):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    fixtures = {name: planning_fixture(name) for name in SCENARIOS}
    fixtures["direct_only_existing_surface"] = direct_only_planning_fixture()
    results = {}
    with no_admission_effects():
        plans = {name: build_plan(fixture) for name, fixture in fixtures.items()}
        for name, fixture in fixtures.items():
            plan = plans[name]
            before = _snapshot(fixture, plan)
            samples, fingerprints = [], []
            for _ in range(repetitions):
                timings = {}
                admission = build(fixture, plan, timings=timings)
                assert set(timings) == set(owner.TIMING_FIELDS)
                samples.append(timings)
                fingerprints.append(admission.fingerprint)
            assert len(set(fingerprints)) == 1
            assert validate(admission.as_dict(), fixture, plan) == admission
            assert before == _snapshot(fixture, plan)
            results[name] = {
                "admission": admission.as_dict(),
                "capability_eligible_scenario_ids": list(admission.capability_eligible_scenario_ids),
                "execution_plan_fingerprint": plan.fingerprint,
                "compile_receipt_kind": "synthetic_provider_evidence_only",
                "fixture_surface": "preexisting_typed_direct_state_and_credential_argument_surface"
                    if name == "direct_only_existing_surface" else "frozen_BANK_surface",
                "deterministic": True, "parent_lineage_unchanged": True,
                "performance": {key: {
                    "median_ms": round(statistics.median(s[key] for s in samples) * 1000, 6),
                    "max_ms": round(max(s[key] for s in samples) * 1000, 6),
                } for key in owner.TIMING_FIELDS},
            }

        fixture = fixtures["preserve_base_compatibility"]
        plan = plans["preserve_base_compatibility"]
        admission = build(fixture, plan)
        absent_reflection = build(fixture, plan, reflection_descriptor=None)
        negatives = {
            "reflection_missing": {
                "status": absent_reflection.status,
                "admitted_scenarios": len(absent_reflection.admitted_scenarios),
                "blocked_scenarios": len(absent_reflection.blocked_scenarios),
                "capability_eligible_scenario_ids": list(absent_reflection.capability_eligible_scenario_ids),
                "getter_fallback_created": False,
            },
            "runtime_authority_missing": {
                "status": "diagnostic_execution_authority_missing",
                "caller_authored_authority": False,
                "admitted_scenarios": len(admission.admitted_scenarios),
            },
            "console_missing": {
                "capability": "deterministic_console_input",
                "status": "unavailable", "stdin_pipe_sufficient": False,
                "adapter_created": False,
            },
        }
        for field in (
                "execution_authorized", "java_execution_authorized", "reflection_authorized",
                "console_authorized", "diagnostic_harness_generation_authorized",
                "product_write_authority", "repository_write_authority", "test_write_authority",
                "reflection_write_authority", "write_authority", "apply_authority",
                "network_authorized"):
            payload = deepcopy(admission.as_dict())
            payload[field] = True
            negatives["forbidden_" + field] = _negative(lambda payload=payload:
                validate(payload, fixture, plan), {"admission_authority_escalation"})
        for field, value in (("shell_command", "java DiagnosticHarness"),
                ("test_file", "SavingAccountBehaviorTest.java"),
                ("java_source", "class DiagnosticHarness {}")):
            payload = deepcopy(admission.as_dict())
            payload[field] = value
            negatives["forbidden_" + field] = _negative(lambda payload=payload:
                validate(payload, fixture, plan), {"admission_invalid", "admission_authority_escalation"})
        negatives["stale_compile_receipt"] = _negative(lambda:
            build(fixture, plan, compile_receipt=fixtures["nested"][4]), {"admission_stale"})
        negatives["stale_source"] = _negative(lambda:
            build(fixture, plan, current_source=fixture[1]["current_source"] + b"\n// stale"),
            {"admission_stale"})

    return {
        "phase_id": owner.PHASE_ID,
        "fixture_kind": "synthetic_frozen_semantic_candidate_lineage_and_compile_provider_evidence",
        "scenarios": results, "negative_cases": negatives, "repetitions": repetitions,
        "actual_javac_invocation_count": 0, "actual_version_probe_count": 0,
        "java_execution_count": 0, "reflection_execution_count": 0, "console_open_count": 0,
        "diagnostic_harness_generation_count": 0, "test_generation_count": 0,
        "model_calls": 0, "author_calls": 0, "repository_traversals": 0,
        "source_mutation": False, "product_api_widened": False,
        "real_BANK2_approval_consumed": False, "MainApp_session_touched": False,
        "scope_authority": "diagnostic_behavioral_execution_only",
        "execution_authorized": False, "java_execution_authorized": False,
        "reflection_authorized": False, "console_authorized": False,
        "diagnostic_harness_generation_authorized": False,
        "write_authority": False, "product_write_authority": False,
        "repository_write_authority": False, "apply_authority": False,
        "test_write_authority": False, "reflection_write_authority": False,
        "network_authorized": False,
        "first_remaining_blocker": owner.FIRST_REMAINING_BLOCKER,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay(repetitions=args.repetitions)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n")
    print(json.dumps({
        "phase_id": result["phase_id"],
        "scenarios": {name: {"status": row["admission"]["status"],
            "admitted_scenarios": len(row["admission"]["admitted_scenarios"]),
            "blocked_scenarios": len(row["admission"]["blocked_scenarios"]),
            "capable_scenarios": len(row["capability_eligible_scenario_ids"]),
            "performance": row["performance"]} for name, row in result["scenarios"].items()},
        "negative_cases": result["negative_cases"],
        "java_execution_count": 0, "reflection_execution_count": 0,
        "first_remaining_blocker": result["first_remaining_blocker"],
    }, indent=2))
