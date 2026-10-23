"""Replay exact runtime policy authority with synthetic provenance and no effects.

Compile receipts are illustrative normalization-only provider records. Source
records are issued by the separate process-local synthetic authority seam;
their report JSON cannot be reused as authenticated authority. This script
never imports an executed synthetic Java probe or consumes a BANK session.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests._preflight_runtime1_guard import no_runtime_effects

# Effect denial starts before any project owner or frozen fixture import.
with no_runtime_effects(strict=False):
    from core import runtime_diagnostic_authorization as owner
    from core import read_only_reflection as reflection
    from scripts.replay_patch_candidate_behavior_exec_admit1 import lineage
    from scripts.replay_patch_candidate_behavior_exec_plan1 import (
        build as build_plan, direct_only_planning_fixture, planning_fixture,
    )
    from scripts.replay_oop_intent_detect2 import BANK


def build(fixture, execution_plan, **changes):
    return owner.build_runtime_diagnostic_authorization(execution_plan,
        **lineage(fixture, **changes))


def validate(authorization, fixture, execution_plan, **changes):
    return owner.validate_runtime_diagnostic_authorization(authorization,
        execution_plan=execution_plan, **lineage(fixture, **changes))


def source(fixture, execution_plan, scenario_ids, *, fixture_id,
        source_kind="explicit_human_runtime_authorization", **changes):
    return owner.issue_synthetic_runtime_authorization_source(execution_plan,
        scenario_ids=tuple(scenario_ids), fixture_id=fixture_id,
        source_kind=source_kind, **lineage(fixture, **changes))


def _snapshot(fixture, execution_plan):
    scope, fresh, candidate, materialized, receipt, specification = fixture
    return (scope.to_json(), fresh["plan"].to_json(), candidate.to_json(),
        materialized.to_json(), receipt.to_json(), specification.to_json(),
        fresh["current_source"], execution_plan.to_json())


def _negative(operation):
    try:
        operation()
    except ValueError as exc:
        return {"status": getattr(exc, "code", str(exc)), "authorization_accepted": False}
    raise AssertionError("negative runtime diagnostic authorization accepted")


def _rehashed(payload):
    result = deepcopy(payload)
    result.pop("authorization_fingerprint", None)
    result["authorization_fingerprint"] = sha256(json.dumps(result,
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")).hexdigest()
    return result


def replay(*, repetitions=3):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    with no_runtime_effects() as guard:
        # Supplying BANK bytes selects pure normalization rather than any
        # compiler measurement fixture. All data is illustrative in-memory.
        fixtures = {
            "BANK_preserve_base_compatibility": planning_fixture(source=BANK),
            "BANK_nested": planning_fixture("nested", source=BANK),
            "direct_only_existing_surface": direct_only_planning_fixture(),
        }
        results, sources = {}, {}
        for name, fixture in fixtures.items():
            plan = build_plan(fixture)
            before = _snapshot(fixture, plan)
            selected = next(s.scenario_id for s in plan.scenarios
                if s.purpose == "successful_transfer")
            trusted = source(fixture, plan, (selected,),
                fixture_id="synthetic.PREFLIGHT.RUNTIME.1." + name)
            absent = build(fixture, plan)
            assert absent.diagnostic_runtime_policy_authorized is False
            samples, fingerprints = [], []
            for _ in range(repetitions):
                timings = {}
                authorization = build(fixture, plan, authorization_source=trusted,
                    timings=timings)
                assert set(timings) == set(owner.TIMING_FIELDS)
                assert authorization.diagnostic_runtime_policy_authorized is True
                assert authorization.runtime_executor_available is False
                samples.append(timings)
                fingerprints.append(authorization.fingerprint)
            assert len(set(fingerprints)) == 1
            assert validate(authorization.as_dict(), fixture, plan,
                authorization_source=trusted) == authorization
            assert before == _snapshot(fixture, plan)
            sources[name] = trusted, authorization, fixture, plan
            results[name] = {
                "absent_source": absent.as_dict(),
                "synthetic_authorized": authorization.as_dict(),
                "synthetic_source_report": trusted.as_dict(),
                "selected_scenario_ids": [selected],
                "compile_receipt_kind": "synthetic_provider_evidence_normalization_only",
                "deterministic": True, "parent_lineage_unchanged": True,
                "performance": {key: {
                    "median_ms": round(statistics.median(s[key] for s in samples) * 1000, 6),
                    "max_ms": round(max(s[key] for s in samples) * 1000, 6),
                } for key in owner.TIMING_FIELDS},
            }

        trusted, authorization, fixture, plan = sources["BANK_preserve_base_compatibility"]
        negatives = {}
        negatives["forged_human_json"] = _negative(lambda:
            build(fixture, plan, authorization_source=trusted.as_dict()))
        negatives["overbroad_scenario"] = _negative(lambda:
            source(fixture, plan, ("BANK.not_in_execution_plan",),
                fixture_id="synthetic.overbroad"))
        for field in ("repository_write_authority", "product_write_authority",
                "reflection_write_authority", "test_write_authority", "apply_authority"):
            payload = authorization.as_dict()
            payload[field] = True
            negatives[field] = _negative(lambda payload=payload:
                validate(_rehashed(payload), fixture, plan, authorization_source=trusted))
        for field, value in (("shell_command", "forbidden command payload"),
                ("network_authorized", True), ("console_capability_available", True)):
            payload = authorization.as_dict()
            payload[field] = value
            negatives[field] = _negative(lambda payload=payload:
                validate(_rehashed(payload), fixture, plan, authorization_source=trusted))
        for field in ("authorized_invocation_targets", "authorized_observation_targets"):
            payload = authorization.as_dict()
            payload[field].append({"extra_target": "unplanned_debug_target"})
            negatives[field] = _negative(lambda payload=payload:
                validate(_rehashed(payload), fixture, plan, authorization_source=trusted))
        negatives["stale_source_bytes"] = _negative(lambda:
            validate(authorization, fixture, plan, authorization_source=trusted,
                current_source=fixture[1]["current_source"] + b"\n// changed candidate input"))
        replacement = source(fixture, plan, authorization.authorized_scenario_ids,
            fixture_id="synthetic.changed_authority_source")
        negatives["stale_authority_source"] = _negative(lambda:
            validate(authorization, fixture, plan, authorization_source=replacement))

        source_kinds = {}
        for kind in ("explicit_typed_task_runtime_authority",
                "explicit_human_runtime_authorization", "frozen_policy_pre_authorization"):
            record = source(fixture, plan, authorization.authorized_scenario_ids,
                fixture_id="synthetic.source_kind." + kind, source_kind=kind)
            projected = build(fixture, plan, authorization_source=record)
            assert projected.diagnostic_runtime_policy_authorized is True
            source_kinds[kind] = {"synthetic_only": True,
                "authorization_source_kind": projected.authorization_source_kind,
                "policy_authorized": projected.diagnostic_runtime_policy_authorized,
                "status": projected.status, "runtime_executor_available": False}

        interest_scenario = next(s for s in plan.scenarios
            if s.purpose == "savings_interest")
        interest = interest_scenario.scenario_id
        # These are exact frozen REFLECT parents, issued independently of the
        # new authorization owner. Authorization has no request-creation seam.
        interest_requests = tuple(reflection.build_read_only_reflection_request(plan,
            scenario_id=interest, observation_id=observation.observation_id,
            **lineage(fixture)) for observation in interest_scenario.observations
            if observation.mechanism == "read_only_reflection")
        interest_source = source(fixture, plan, (interest,),
            fixture_id="synthetic.interest_console_missing", reflection_requests=interest_requests)
        interest_authorization = build(fixture, plan, authorization_source=interest_source,
            reflection_requests=interest_requests)
        assert validate(interest_authorization.as_dict(), fixture, plan,
            authorization_source=interest_source, reflection_requests=interest_requests) == interest_authorization
        assert interest_authorization.console_capability_available is False
        assert interest_authorization.runtime_executor_available is False
        assert not guard.denied_attempts, guard.denied_attempts
        return {
            "phase_id": owner.PHASE_ID, "schema_version": owner.SCHEMA_VERSION,
            "fixture_kind": "synthetic_frozen_semantic_lineage_and_authenticated_fixture_authority_only",
            "scenarios": results, "negative_cases": negatives,
            "source_kinds": source_kinds,
            "interest_with_synthetic_source": interest_authorization.as_dict(),
            "interest_external_REFLECT_request_parent_count": len(interest_requests),
            "repetitions": repetitions, "effect_guard_from_project_import": True,
            "effect_guard_from_fixture_start": True, "denied_effect_attempts": dict(guard.denied_attempts),
            "java_execution_count": 0, "reflection_execution_count": 0,
            "console_open_count": 0, "actual_javac_invocation_count": 0,
            "diagnostic_harness_generation_count": 0, "test_generation_count": 0,
            "model_calls": 0, "author_calls": 0, "repository_traversals": 0,
            "source_mutation_count": 0, "real_BANK2_approval_consumed": False,
            "MainApp_session_touched": False, "real_runtime_source_available": False,
            "prior_EXEC_ADMIT1_breach": {
                "disclosed_synthetic_verification_execution_breach_count": 1,
                "java_process_count": 1, "javac_count": 1, "actual_synthetic_field_reads": 14,
                "BANK_candidate_execution_count": 0, "part_of_this_phase": False,
            },
            "first_real_remaining_blocker": "diagnostic_execution_authority_missing",
            "first_synthetic_authorized_remaining_blocker": "runtime_executor_capability_missing",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay(repetitions=args.repetitions)
    # Governance artifact serialization happens after the pure consumer guard;
    # this is not a product/repository execution effect or authority grant.
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False,
            indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"phase_id": result["phase_id"],
        "scenarios": {name: {"absent_source_status": row["absent_source"]["status"],
            "synthetic_status": row["synthetic_authorized"]["status"],
            "selected_scenario_ids": row["selected_scenario_ids"],
            "performance": row["performance"]} for name, row in result["scenarios"].items()},
        "negative_cases": result["negative_cases"],
        "java_execution_count": result["java_execution_count"],
        "reflection_execution_count": result["reflection_execution_count"],
        "first_real_remaining_blocker": result["first_real_remaining_blocker"],
        "first_synthetic_authorized_remaining_blocker": result["first_synthetic_authorized_remaining_blocker"],
    }, indent=2))
