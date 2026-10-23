"""Replay bounded behavioral execution planning without executing Java.

Every public-path fixture reuses the frozen synthetic candidate and compile
receipt construction. Compiler evidence is illustrative provider evidence;
this replay measures Python planning latency only.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.behavioral_evidence_execution_plan import (
    FIRST_REMAINING_BLOCKER, PHASE_ID, TIMING_FIELDS,
    build_behavioral_evidence_execution_plan,
    validate_behavioral_evidence_execution_plan,
)
from core.behavioral_validation_specification import project_behavioral_validation_specification
from core.structural_candidate_materialization import materialize_structural_candidate
from core.structural_compile_validation import CompilerResult, JavacIdentity, normalize_structural_compile_result
from core.structural_patch_author import normalize_structural_author_output
from scripts.replay_patch_candidate_behavior_spec1 import (
    no_specification_effects, synthetic_compiled_case,
)
from scripts.replay_patch_candidate_materialize1 import SCENARIOS, synthetic_candidate_case
from scripts.replay_oop_intent_detect2 import BANK


@contextmanager
def no_execution_planning_effects():
    """Forbid providers, Java/compiler/processes, network, I/O and traversal."""
    with no_specification_effects(), ExitStack() as guards:
        for target in ("pty.openpty", "os.popen"):
            # Windows Python does not provide pty. No adapter is created by
            # this phase; all process/file/socket paths are already guarded.
            if target.startswith("pty.") and sys.platform == "win32":
                continue
            guards.enter_context(patch(target,
                side_effect=AssertionError("execution planner attempted a forbidden effect")))
        yield


def planning_fixture(name="preserve_base_compatibility", *, source=None):
    if source is None:
        fixture = synthetic_compiled_case(name)
    else:
        scope, fresh, candidate = synthetic_candidate_case(name, source=source)
        with no_execution_planning_effects():
            materialized = materialize_structural_candidate(candidate, admitted_scope=scope, **fresh)
            identity = JavacIdentity(str(Path("C:/trusted/javac.exe")), "a" * 64, "javac 23.0.2")
            receipt = normalize_structural_compile_result(materialized,
                compiler_result=CompilerResult(compiler=identity, exit_code=0),
                candidate=candidate, admitted_scope=scope, **fresh)
        fixture = scope, fresh, candidate, materialized, receipt
    scope, fresh, candidate, materialized, receipt = fixture
    with no_execution_planning_effects():
        specification = project_behavioral_validation_specification(receipt,
            materialized=materialized, candidate=candidate, admitted_scope=scope, **fresh)
    return (*fixture, specification)


def direct_only_planning_fixture(*, transfer_name="transferToSavings", extra_transfer=False):
    """Fully validate a synthetic existing direct surface through frozen owners.

    This is a separate illustrative input, never a getter or source edit to the
    BANK candidate. Its source and typed PLAN already expose exact ordinary and
    savings observations and credential input before planning begins.
    """
    import scripts.replay_patch_author_structural1 as author_replay
    original = author_replay.synthetic_planner_proposal

    def direct_surface(*args, **kwargs):
        proposal = original(*args, **kwargs)
        direct = replace(proposal, logical_creations=tuple(replace(creation,
            definitions=tuple(replace(definition, visibility="public")
                if "subclass_owned_state" in definition.roles else
                replace(definition, parameters=(("double", "rate"), ("double", "period"),
                    ("String", "providedPassword")))
                if "savings_interest_behavior" in definition.roles else
                replace(definition, name=transfer_name)
                if "savings_funding_transition" in definition.roles else definition
                for definition in creation.definitions)) for creation in proposal.logical_creations))
        if not extra_transfer:
            return direct
        additional = next(replace(definition, name="moveToSavings", definition_id="")
            for creation in direct.logical_creations for definition in creation.definitions
            if "savings_funding_transition" in definition.roles)
        return replace(direct,
            logical_creations=tuple(replace(creation,
                definitions=(*creation.definitions, additional))
                if any("savings_funding_transition" in d.roles for d in creation.definitions)
                else creation for creation in direct.logical_creations),
            capability_coverage=tuple(replace(coverage,
                planned_definitions=(*coverage.planned_definitions, additional.identity))
                if coverage.code == "savings_funding_transition" else coverage
                for coverage in direct.capability_coverage))

    source = BANK.replace("  void deposit",
        "  public double balanceForEvidence() { return balance; }\n  void deposit")
    with patch.object(author_replay, "synthetic_planner_proposal", direct_surface):
        scope, fresh = author_replay.synthetic_case(source=source)
    output = author_replay.synthetic_author_output(scope)
    for operation in output["candidate"]["operations"]:
        if operation["source_text"]:
            operation["source_text"] = operation["source_text"].replace(
                "private double savingBalance;", "public double savingBalance;").replace(
                "System.console().readLine()", "providedPassword").replace(
                "transferToSavings", transfer_name)
            if extra_transfer and "class SavingAccount" in operation["source_text"]:
                debit = next(a.definition.name for a in scope.definition_allowances
                    if "base_balance_debit" in a.definition.roles)
                additional_source = (
                    "  public boolean moveToSavings(double amount, String providedPassword) {\n"
                    "    if (!verifySavingsPassword(providedPassword)) return false;\n"
                    f"    if (!{debit}(amount)) return false;\n"
                    "    savingBalance += amount;\n    return true;\n  }\n"
                )
                operation["source_text"] = operation["source_text"].rsplit("}", 1)[0] + additional_source + "}\n"
    with no_execution_planning_effects():
        result = normalize_structural_author_output(admitted_scope=scope, author_output=output, **fresh)
        assert result.candidate is not None, (result.status, result.reason)
        candidate = result.candidate
        materialized = materialize_structural_candidate(candidate, admitted_scope=scope, **fresh)
        identity = JavacIdentity(str(Path("C:/trusted/javac.exe")), "a" * 64, "javac 23.0.2")
        receipt = normalize_structural_compile_result(materialized,
            compiler_result=CompilerResult(compiler=identity, exit_code=0),
            candidate=candidate, admitted_scope=scope, **fresh)
        specification = project_behavioral_validation_specification(receipt,
            materialized=materialized, candidate=candidate, admitted_scope=scope, **fresh)
    assert not specification.observation_gaps and not specification.execution_harness_constraints
    return scope, fresh, candidate, materialized, receipt, specification


def build(fixture, **changes):
    scope, fresh, candidate, materialized, receipt, specification = fixture
    return build_behavioral_evidence_execution_plan(**{
        "specification": specification, "compile_receipt": receipt,
        "materialized": materialized, "candidate": candidate,
        "admitted_scope": scope, **fresh, **changes,
    })


def validate(execution_plan, fixture, **changes):
    scope, fresh, candidate, materialized, receipt, specification = fixture
    return validate_behavioral_evidence_execution_plan(execution_plan, **{
        "specification": specification, "compile_receipt": receipt,
        "materialized": materialized, "candidate": candidate,
        "admitted_scope": scope, **fresh, **changes,
    })


def _negative(operation, expected):
    try:
        operation()
    except ValueError as exc:
        code = getattr(exc, "code", str(exc))
        assert code in expected, (code, expected)
        return {"status": code, "execution_plan_accepted": False}
    raise AssertionError("negative execution plan was accepted")


def replay(*, repetitions=5):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    fixtures = {name: planning_fixture(name) for name in SCENARIOS}
    fixtures["direct_only_existing_surface"] = direct_only_planning_fixture()
    scenarios = {}
    with no_execution_planning_effects():
        for name, fixture in fixtures.items():
            scope, fresh, candidate, materialized, receipt, specification = fixture
            before = (scope.to_json(), fresh["plan"].to_json(), candidate.to_json(),
                materialized.to_json(), receipt.to_json(), specification.to_json(), fresh["current_source"])
            samples, fingerprints = [], []
            for _ in range(repetitions):
                timings = {}
                plan = build(fixture, timings=timings)
                assert validate(plan.as_dict(), fixture) == plan
                assert set(timings) == set(TIMING_FIELDS)
                samples.append(timings)
                fingerprints.append(plan.fingerprint)
            assert len(set(fingerprints)) == 1
            assert before == (scope.to_json(), fresh["plan"].to_json(), candidate.to_json(),
                materialized.to_json(), receipt.to_json(), specification.to_json(), fresh["current_source"])
            scenarios[name] = {
                "execution_plan": plan.as_dict(),
                "compile_receipt_kind": "synthetic_provider_evidence_only",
                "fixture_surface": "preexisting_typed_direct_state_and_credential_argument_surface"
                    if name == "direct_only_existing_surface" else "frozen_BANK_surface",
                "behavioral_specification_fingerprint": specification.fingerprint,
                "deterministic": True, "source_bytes_unchanged": True,
                "candidate_unchanged": True, "materialization_unchanged": True,
                "historical_plan_unchanged": True, "oracle_unchanged": True,
                "performance": {key: {
                    "median_ms": round(statistics.median(s[key] for s in samples) * 1000, 6),
                    "max_ms": round(max(s[key] for s in samples) * 1000, 6),
                } for key in TIMING_FIELDS},
            }

        fixture = fixtures["preserve_base_compatibility"]
        plan = build(fixture)
        negatives = {}
        for field, value in (("reflection_authorized", True), ("console_authorized", True),
                ("java_execution_authorized", True), ("execution_authorized", True),
                ("diagnostic_harness_generation_authorized", True),
                ("test_write_authority", True), ("write_authority", True), ("apply_authority", True)):
            payload = deepcopy(plan.as_dict())
            payload[field] = value
            negatives["forbidden_" + field] = _negative(lambda payload=payload:
                validate(payload, fixture), {"execution_plan_authority_escalation"})
        for field, value in (("java_source", "class DiagnosticHarness {}"),
                ("shell_command", "java DiagnosticHarness"), ("java_command", ["java", "SavingAccount"])):
            payload = deepcopy(plan.as_dict())
            payload[field] = value
            negatives["forbidden_" + field] = _negative(lambda payload=payload:
                validate(payload, fixture), {"execution_plan_invalid"})
        for kind in ("reflection_write", "unbound_method", "oracle_drift", "tolerance_drift", "missing_obligation"):
            payload = deepcopy(plan.as_dict())
            if kind == "reflection_write":
                observation = next(o for s in payload["scenarios"] for o in s["observations"]
                    if o["mechanism"] == "read_only_reflection")
                observation["reflection_operation"] = "write_field"
                expected = {"execution_plan_authority_escalation"}
            else:
                expected = {"execution_plan_stale", "execution_plan_oracle_drift", "execution_plan_invalid"}
                if kind == "unbound_method":
                    payload["scenarios"][0]["invocation"]["target"]["name"] = "unboundMethod"
                elif kind == "oracle_drift":
                    payload["obligations"][0]["oracle"]["expected_observations"].append("three_password_attempts")
                elif kind == "tolerance_drift":
                    payload["scenarios"][0]["comparison_policy"]["absolute_tolerance"] = 100.0
                else:
                    payload["obligations"] = payload["obligations"][1:]
            negatives[kind] = _negative(lambda payload=payload: validate(payload, fixture), expected)
        negatives["stale_compile_receipt"] = _negative(lambda:
            build(fixture, compile_receipt=fixtures["nested"][4]), {"execution_plan_stale"})
        negatives["stale_source"] = _negative(lambda:
            build(fixture, current_source=fixture[1]["current_source"] + b"\n// stale"),
            {"execution_plan_stale"})
        reflection = next(o for s in plan.as_dict()["scenarios"] for o in s["observations"]
            if o["mechanism"] == "read_only_reflection")
        negatives["private_state_no_reflection_authority"] = {
            "status": "blocked_missing_capability", "capability": "read_only_reflection",
            "exact_field": reflection["target"], "getter_proposed": False,
        }
        negatives["console_without_typed_adapter"] = {
            "status": "blocked_missing_capability", "capability": "deterministic_console_input",
            "stdin_pipe_sufficient": False, "adapter_created": False,
        }

    return {
        "phase_id": PHASE_ID,
        "fixture_kind": "synthetic_frozen_semantic_candidate_lineage_and_compile_provider_evidence",
        "scenarios": scenarios, "negative_cases": negatives, "repetitions": repetitions,
        "actual_javac_invocation_count": 0, "actual_version_probe_count": 0,
        "java_execution_count": 0, "reflection_execution_count": 0, "console_open_count": 0,
        "diagnostic_harness_generation_count": 0, "test_generation_count": 0,
        "model_calls": 0, "author_calls": 0, "repository_traversals": 0,
        "source_mutation": False, "product_api_widened": False,
        "real_BANK2_approval_consumed": False, "MainApp_session_touched": False,
        "authority": "behavioral_execution_plan_only", "reflection_authorized": False,
        "console_authorized": False, "java_execution_authorized": False,
        "diagnostic_harness_generation_authorized": False, "test_write_authority": False,
        "execution_authorized": False, "write_authority": False, "apply_authority": False,
        "first_remaining_blocker": FIRST_REMAINING_BLOCKER,
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
        "scenarios": {name: {"status": row["execution_plan"]["status"],
            "scenario_count": len(row["execution_plan"]["scenarios"]),
            "performance": row["performance"]} for name, row in result["scenarios"].items()},
        "negative_cases": result["negative_cases"],
        "actual_javac_invocation_count": 0, "java_execution_count": 0,
        "first_remaining_blocker": result["first_remaining_blocker"],
    }, indent=2))
