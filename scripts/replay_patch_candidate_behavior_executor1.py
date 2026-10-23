"""Replay EXECUTOR.1's fail-closed boundary without runtime effects.

Frozen runtime policy forbids arbitrary filesystem and network effects. The
local executor cannot technically isolate candidate Java, so the user-defined
capability-incomplete stop condition applies before projection, rendering or
launch. The strict no-runtime guard is appropriate only for this blocked path;
a future runnable adapter must instead count exact owned launches and reject
incidental launches. These fixtures use normalization-only compiler evidence.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import behavioral_diagnostic_executor as owner
    from scripts.replay_patch_candidate_behavior_exec_admit1 import (
        build as build_admission, lineage,
    )
    from scripts.replay_patch_candidate_behavior_exec_plan1 import (
        build as build_plan, direct_only_planning_fixture, planning_fixture,
    )
    from scripts.replay_oop_intent_detect2 import BANK
    from tests.test_preflight_runtime1 import (
        build as build_authorization, external_reflection_parents, is_direct,
        issue, rehashed, snapshot,
    )


def build_case(name="preserve_base_compatibility"):
    fixture = (direct_only_planning_fixture() if name == "direct" else
        planning_fixture(name, source=BANK))
    plan = build_plan(fixture)
    admission = build_admission(fixture, plan,
        **({"reflection_descriptor": None} if name == "direct" else {}))
    return fixture, plan, admission


def execution_inputs(case, *, source=None, **changes):
    fixture, plan, admission = case
    return {
        **lineage(fixture), "execution_plan": plan,
        "behavioral_admission": admission, "authorization_source": source,
        "reflection_requests": external_reflection_parents(case, source),
        **({"reflection_descriptor": None} if is_direct(case) else {}), **changes,
    }


def execute(authorization, case, scenario_id, *, source=None, **changes):
    return owner.execute_behavioral_diagnostic(authorization,
        scenario_id=scenario_id, **execution_inputs(case, source=source, **changes))


def validate(receipt, authorization, case, scenario_id, *, source=None, **changes):
    return owner.validate_behavioral_diagnostic_execution_receipt(receipt,
        authorization=authorization, scenario_id=scenario_id,
        **execution_inputs(case, source=source, **changes))


def _negative(operation):
    try:
        operation()
    except owner.BehavioralDiagnosticExecutionError as exc:
        assert exc.java_execution_count == 0
        return {"status": exc.code, "reason": exc.reason,
            "java_execution_count": exc.java_execution_count}
    raise AssertionError("negative diagnostic execution was accepted")


def replay(*, repetitions=3):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    with no_runtime_effects() as guard:
        case = build_case()
        before = snapshot(case)
        scenarios, trusted_records = {}, {}
        for purpose in ("wrong_credential_transfer", "successful_transfer", "unsuccessful_debit"):
            selected = next(s for s in case[1].scenarios if s.purpose == purpose)
            source = issue(case, purposes=(purpose,),
                fixture_id="synthetic.EXECUTOR.1." + purpose)
            authorization = build_authorization(case, source=source)
            samples, fingerprints = [], []
            for _ in range(repetitions):
                timings = {}
                receipt = execute(authorization, case, selected.scenario_id,
                    source=source, timings=timings)
                assert receipt.status == "runtime_executor_capability_incomplete"
                assert receipt.execution_completed is False
                assert validate(receipt, authorization, case, selected.scenario_id,
                    source=source) == receipt
                assert set(timings) == set(owner.TIMING_FIELDS)
                samples.append(timings)
                fingerprints.append(receipt.fingerprint)
            assert len(set(fingerprints)) == 1
            trusted_records[purpose] = source, authorization, receipt, selected.scenario_id
            scenarios[purpose] = {
                "synthetic_only": True, "policy_authorized": True,
                "compile_receipt_kind": "synthetic_provider_evidence_normalization_only",
                "execution_receipt": receipt.as_dict(), "deterministic": True,
                "performance": {key: {
                    "median_ms": round(statistics.median(s[key] for s in samples) * 1000, 6),
                    "max_ms": round(max(s[key] for s in samples) * 1000, 6),
                } for key in owner.TIMING_FIELDS},
            }

        source, authorization, receipt, scenario_id = trusted_records["successful_transfer"]
        absent = build_authorization(case)
        real_bank = execute(absent, case, scenario_id)
        assert real_bank.status == "diagnostic_execution_authority_missing"
        interest_source = issue(case, purposes=("savings_interest",),
            fixture_id="synthetic.EXECUTOR.1.console-unavailable")
        interest_authorization = build_authorization(case, source=interest_source)
        interest_id = interest_authorization.authorized_scenario_ids[0]
        interest = execute(interest_authorization, case, interest_id, source=interest_source)
        assert interest.status == "runtime_executor_console_unavailable"
        direct = build_case("direct")
        direct_absent = build_authorization(direct, reflection_descriptor=None)
        direct_id = next(s.scenario_id for s in direct[1].scenarios
            if s.purpose == "successful_transfer")
        direct_negative = execute(direct_absent, direct, direct_id)
        assert direct_negative.status == "diagnostic_execution_authority_missing"

        negatives = {
            "missing_authorization": _negative(lambda: execute(None, case, scenario_id, source=source)),
            "unknown_scenario": _negative(lambda: execute(authorization, case, "BANK.unplanned", source=source)),
            "stale_source_bytes": _negative(lambda: execute(authorization, case, scenario_id,
                source=source, current_source=case[0][1]["current_source"] + b"\n// stale")),
            "exported_receipt": _negative(lambda: validate(receipt.as_dict(), authorization,
                case, scenario_id, source=source)),
        }
        for key, value in (("shell_command", "cmd.exe /c arbitrary"),
                ("network_authorized", True), ("repository_write_authority", True),
                ("reflection_write_authority", True), ("getDeclaredFields", True)):
            payload = deepcopy(authorization.as_dict())
            payload[key] = value
            negatives[key] = _negative(lambda payload=payload:
                execute(rehashed(payload), case, scenario_id, source=source))

        assert snapshot(case) == before
        assert not guard.denied_attempts, guard.denied_attempts
        return {
            "phase_id": owner.PHASE_ID, "schema_version": owner.SCHEMA_VERSION,
            "status": "runtime_executor_capability_incomplete",
            "executor_descriptor": owner.get_bounded_java_diagnostic_executor_descriptor().as_dict(),
            "fixture_kind": "synthetic_frozen_lineage_and_authenticated_fixture_authority_only",
            "repetitions": repetitions, "synthetic_authorized_scenarios": scenarios,
            "performance_sampling_limitation": (
                "One Python-only sample per scenario; median equals maximum and variability is not measured."
                if repetitions == 1 else
                "Repeated in-memory Python reconstruction only; compiler/JVM runtime latency is unmeasured."),
            "real_BANK_without_operational_source": real_bank.as_dict(),
            "direct_only_without_source": direct_negative.as_dict(),
            "interest_with_synthetic_source": interest.as_dict(), "negative_cases": negatives,
            "strict_guard_reason": "Required hard filesystem/network isolation is unavailable; no adapter is eligible to launch.",
            "effect_guard_from_project_import": True, "effect_guard_from_fixture_start": True,
            "denied_effect_attempts": dict(guard.denied_attempts),
            "parent_lineage_unchanged": True, "oracle_evaluated": False,
            "unexecuted_runtime_stages": {
                status: "not_exercised_required_isolation_unavailable" for status in (
                    "harness_compile_failed", "runtime_launch_failed", "timeout", "output_overflow",
                    "observation_failed", "authorized_action_threw")
            },
            "java_execution_count": 0, "reflection_execution_count": 0,
            "console_open_count": 0, "actual_javac_invocation_count": 0,
            "diagnostic_harness_generation_count": 0, "test_generation_count": 0,
            "model_calls": 0, "author_calls": 0, "repository_traversals": 0,
            "source_mutation_count": 0, "synthetic_scenarios_actually_executed": [],
            "real_BANK_scenarios_actually_executed": [], "real_BANK2_approval_consumed": False,
            "MainApp_session_touched": False, "real_runtime_source_available": False,
            "first_real_remaining_blocker": "diagnostic_execution_authority_missing",
            "first_synthetic_authorized_remaining_blocker": "runtime_executor_capability_incomplete",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay(repetitions=args.repetitions)
    # Optional governance serialization occurs after the consumer effect guard.
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False,
            indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    summary = {key: result[key] for key in ("phase_id", "status",
        "executor_descriptor", "negative_cases", "java_execution_count",
        "first_real_remaining_blocker", "first_synthetic_authorized_remaining_blocker")}
    summary["synthetic_authorized_scenarios"] = {purpose: {
        "status": row["execution_receipt"]["status"],
        "scenario_id": row["execution_receipt"]["scenario_id"],
        "performance": row["performance"],
    } for purpose, row in result["synthetic_authorized_scenarios"].items()}
    print(json.dumps(summary, indent=2))
