"""Replay pure exact reflection authorization; never execute BANK or Java.

The existing frozen synthetic compile receipt is supplied evidence. Adapter
execution is verified separately by the isolated synthetic infrastructure suite.
This replay emits requests and architecture truth without runtime observations.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.read_only_reflection import (
    PHASE_ID, TIMING_FIELDS, build_read_only_reflection_request,
    get_read_only_reflection_capability_descriptor,
    reconstruct_diagnostic_capability_availability,
    validate_read_only_reflection_request,
)
from core.behavioral_evidence_execution_plan import FIRST_REMAINING_BLOCKER
from scripts.replay_patch_candidate_behavior_exec_plan1 import (
    build, no_execution_planning_effects, planning_fixture, validate,
)
from scripts.replay_patch_candidate_materialize1 import SCENARIOS


def _payload(record):
    return record.as_dict() if hasattr(record, "as_dict") else asdict(record) if is_dataclass(record) else record


def reflection_inputs(fixture, execution_plan):
    scope, fresh, candidate, materialized, receipt, specification = fixture
    return {"execution_plan": execution_plan, "specification": specification,
        "compile_receipt": receipt, "materialized": materialized,
        "candidate": candidate, "admitted_scope": scope, **fresh}


def _negative(operation):
    try:
        operation()
    except ValueError as exc:
        return {"status": getattr(exc, "code", str(exc)), "request_accepted": False}
    raise AssertionError("negative reflection request was accepted")


def replay(*, repetitions=5):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    descriptor = get_read_only_reflection_capability_descriptor()
    fixtures = {name: planning_fixture(name) for name in SCENARIOS}
    layouts = {}
    with no_execution_planning_effects():
        for name, fixture in fixtures.items():
            before = tuple(v.to_json() for v in (fixture[0], fixture[2], fixture[3], fixture[4], fixture[5]))
            source_before = fixture[1]["current_source"]
            plan = build(fixture)
            assert validate(plan, fixture) == plan
            historical_plan = plan.to_json()
            inputs = reflection_inputs(fixture, plan)
            requests = []
            samples, fingerprints = [], []
            for scenario in plan.scenarios:
                for observation in scenario.observations:
                    if observation.mechanism != "read_only_reflection":
                        continue
                    request = build_read_only_reflection_request(**inputs,
                        scenario_id=scenario.scenario_id, observation_id=observation.observation_id)
                    assert validate_read_only_reflection_request(_payload(request), **inputs) == request
                    requests.append(_payload(request))
                    if samples:
                        continue
                    for _ in range(repetitions):
                        timing = {}
                        repeated = build_read_only_reflection_request(**inputs,
                            scenario_id=scenario.scenario_id, observation_id=observation.observation_id,
                            timings=timing)
                        assert repeated == request
                        assert set(timing) == set(TIMING_FIELDS)
                        samples.append(timing)
                        fingerprints.append(repeated.fingerprint)
            assert requests and len(set(fingerprints)) == 1
            reconstruction = reconstruct_diagnostic_capability_availability(plan, descriptor=descriptor)
            assert historical_plan == plan.to_json()
            assert source_before == fixture[1]["current_source"]
            assert before == tuple(v.to_json() for v in (fixture[0], fixture[2], fixture[3], fixture[4], fixture[5]))
            layouts[name] = {"historical_execution_plan_fingerprint": plan.fingerprint,
                "compile_receipt_kind": "synthetic_provider_evidence_only",
                "historical_execution_plan_unchanged": True, "source_bytes_unchanged": True,
                "candidate_unchanged": True, "specification_unchanged": True,
                "requests": requests, "request_count": len(requests),
                "architecture_reconstruction": _payload(reconstruction),
                "performance": {key: {"median_ms": round(statistics.median(s[key] for s in samples) * 1000, 6),
                    "max_ms": round(max(s[key] for s in samples) * 1000, 6)} for key in TIMING_FIELDS}}

        fixture = fixtures["preserve_base_compatibility"]
        plan = build(fixture)
        inputs = reflection_inputs(fixture, plan)
        representative = layouts["preserve_base_compatibility"]["requests"][0]
        negatives = {}
        for label, field, value in (
                ("arbitrary_field", "name", "password"),
                ("wrong_owner", "owner", "SavingAccount"),
                ("wrong_type", "declared_type", "int"),
                ("wrong_member_fingerprint", "definition_sha256", "0" * 64),
                ("stale_source", "source_sha256", "0" * 64),
                ("arbitrary_jdk_class", "qualified_owner", "java.lang.System")):
            payload = deepcopy(representative)
            payload["target"][field] = value
            negatives[label] = _negative(lambda payload=payload:
                validate_read_only_reflection_request(payload, **inputs))
        for label, field, value in (
                ("wrong_plan", "execution_plan_fingerprint", "0" * 64),
                ("wrong_scenario", "scenario_id", "other_scenario"),
                ("wrong_observation", "observation_id", "other_observation"),
                ("enumeration", "operation", "enumerate_fields"),
                ("reflective_write", "operation", "write_field"),
                ("private_method_invocation", "operation", "invoke_private_method"),
                ("authority_escalation", "product_mutation_authority", True)):
            payload = deepcopy(representative)
            payload[field] = value
            negatives[label] = _negative(lambda payload=payload:
                validate_read_only_reflection_request(payload, **inputs))

    return {"phase_id": PHASE_ID, "fixture_kind": "pure_frozen_BANK_lineage_request_reconstruction",
        "capability_descriptor": _payload(descriptor), "layouts": layouts,
        "negative_cases": negatives, "repetitions": repetitions,
        "performance_measurement_scope": "pure request authorization and exact target reconstruction",
        "unmeasured_timing_fields": ["adapter_reflection_read_seconds", "value_normalization_seconds",
            "observation_fingerprinting_seconds"],
        "actual_javac_invocation_count": 0, "infrastructure_java_execution_count": 0,
        "BANK_behavioral_java_execution_count": 0, "reflection_execution_count": 0,
        "runtime_observations": [], "synthetic_adapter_execution_proof":
            "tests/test_patch_candidate_behavior_reflect1.py isolated synthetic fixture only",
        "console_open_count": 0, "test_generation_count": 0,
        "model_calls": 0, "author_calls": 0, "repository_traversals": 0,
        "source_mutation": False, "product_api_widened": False,
        "behavioral_execution_admitted": False, "test_write_authority": False,
        "write_authority": False, "apply_authority": False,
        "first_remaining_blocker": FIRST_REMAINING_BLOCKER}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay(repetitions=args.repetitions)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n")
    print(json.dumps({"phase_id": result["phase_id"], "capability_descriptor": result["capability_descriptor"],
        "layouts": {name: {"request_count": row["request_count"], "performance": row["performance"],
            "architecture_reconstruction": row["architecture_reconstruction"]} for name, row in result["layouts"].items()},
        "negative_cases": result["negative_cases"], "BANK_behavioral_java_execution_count": 0,
        "infrastructure_java_execution_count": 0, "first_remaining_blocker": result["first_remaining_blocker"]}, indent=2))
