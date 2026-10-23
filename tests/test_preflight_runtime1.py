"""Exact runtime policy authority is pure, authenticated and never executable.

The import guard starts before project modules are imported. A stricter module
guard remains active before the first lineage fixture is constructed through
the last focused test. Synthetic compile receipts are normalized Python data.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import runtime_diagnostic_authorization as owner
    from core import behavioral_execution_admission as admission_owner
    from core import behavioral_evidence_execution_plan as planner
    from core import read_only_reflection as reflection
    from core.input_understanding import understand_request
    from scripts.replay_patch_candidate_behavior_exec_admit1 import (
        build as build_admission, lineage,
    )
    from scripts.replay_patch_candidate_behavior_exec_plan1 import (
        build as build_plan, direct_only_planning_fixture, planning_fixture,
    )
    from scripts.replay_oop_intent_detect2 import BANK


CAPABLE_PURPOSES = {"wrong_credential_transfer", "successful_transfer", "unsuccessful_debit"}
INTEREST_PURPOSES = {"wrong_credential_interest", "savings_interest"}
SOURCE_KINDS = (
    "explicit_typed_task_runtime_authority", "explicit_human_runtime_authorization",
    "frozen_policy_pre_authorization",
)
FALSE_AUTHORITIES = (
    "repository_write_authority", "product_write_authority", "reflection_write_authority",
    "test_write_authority", "apply_authority", "console_authorized",
)
_REFLECTION_PARENTS = {}
_SOURCE_FIXTURES = {}
_AUTHORIZATION_FIXTURES = {}


@pytest.fixture(scope="module", autouse=True)
def deny_entire_focused_suite():
    with no_runtime_effects() as evidence:
        yield evidence


@pytest.fixture(scope="module")
def cases(deny_entire_focused_suite):
    class Cases(dict):
        def __missing__(self, name):
            # The explicit source branch bypasses any executed-fixture
            # verifier. Everything below uses the preexisting pure owners.
            fixture = (direct_only_planning_fixture() if name == "direct"
                else planning_fixture(name, source=BANK))
            plan = build_plan(fixture)
            admission = build_admission(fixture, plan,
                **({"reflection_descriptor": None} if name == "direct" else {}))
            self[name] = fixture, plan, admission
            return self[name]
    return Cases()


@pytest.fixture(scope="module")
def bank(cases):
    return cases["preserve_base_compatibility"]


def build(case, *, source=None, **changes):
    fixture, plan, admission = case
    # The exact immutable baseline is fixture setup. Negative tests still
    # independently reconstruct every parent in the validator under test.
    cache_key = (id(case), id(source)) if not changes else None
    if cache_key is not None and cache_key in _AUTHORIZATION_FIXTURES:
        return _AUTHORIZATION_FIXTURES[cache_key]
    result = owner.build_runtime_diagnostic_authorization(plan, **{
        **lineage(fixture), "behavioral_admission": admission,
        "authorization_source": source, "reflection_requests": external_reflection_parents(case, source,
            descriptor_missing=changes.get("reflection_descriptor", False) is None),
        **({"reflection_descriptor": None} if is_direct(case) else {}), **changes,
    })
    if cache_key is not None:
        _AUTHORIZATION_FIXTURES[cache_key] = result
    return result


def validate(authorization, case, *, source=None, **changes):
    fixture, plan, admission = case
    return owner.validate_runtime_diagnostic_authorization(authorization, **{
        **lineage(fixture), "execution_plan": plan, "behavioral_admission": admission,
        "authorization_source": source, "reflection_requests": external_reflection_parents(case, source,
            descriptor_missing=changes.get("reflection_descriptor", False) is None),
        **({"reflection_descriptor": None} if is_direct(case) else {}), **changes,
    })


def issue(case, *, purposes=("successful_transfer",), source_kind=SOURCE_KINDS[1],
        fixture_id="synthetic-runtime1-focused", scenario_ids=None, **changes):
    fixture, plan, _ = case
    selected = (tuple(s.scenario_id for s in plan.scenarios if s.purpose in purposes)
        if scenario_ids is None else scenario_ids)
    cache_key = (id(case), selected, source_kind, fixture_id) if not changes else None
    if cache_key is not None and cache_key in _SOURCE_FIXTURES:
        return _SOURCE_FIXTURES[cache_key]
    result = owner.issue_synthetic_runtime_authorization_source(plan,
        **{**lineage(fixture), "scenario_ids": selected, "fixture_id": fixture_id,
            "source_kind": source_kind, "reflection_requests": external_reflection_parents(case,
                scenario_ids=selected, descriptor_missing=changes.get("reflection_descriptor", False) is None),
            **({"reflection_descriptor": None} if is_direct(case) else {}), **changes})
    if cache_key is not None:
        _SOURCE_FIXTURES[cache_key] = result
    return result


def is_direct(case):
    return all(observation.mechanism != "read_only_reflection"
        for scenario in case[1].scenarios for observation in scenario.observations)


def external_reflection_parents(case, source=None, *, scenario_ids=(), descriptor_missing=False):
    fixture, plan, admission = case
    existing = set() if descriptor_missing else {
        request.fingerprint for row in admission.scenarios for request in row.reflection_requests}
    if type(source) is owner.SyntheticRuntimeAuthorizationSource:
        return tuple(request for request in source.scope.reflection_requests
            if request.fingerprint not in existing)
    needed = tuple((scenario.scenario_id, observation.observation_id)
        for scenario in plan.scenarios if scenario.scenario_id in scenario_ids
        for observation in scenario.observations if observation.mechanism == "read_only_reflection")
    result = []
    for scenario_id, observation_id in needed:
        canonical = next((request for row in admission.scenarios for request in row.reflection_requests
            if request.scenario_id == scenario_id and request.observation_id == observation_id), None)
        if canonical is not None and not descriptor_missing:
            continue
        key = plan.fingerprint, scenario_id, observation_id
        if key not in _REFLECTION_PARENTS:
            # Exact existing REFLECT.1 parent artifacts are constructed only
            # by that frozen owner, outside runtime authorization issuance.
            _REFLECTION_PARENTS[key] = reflection.build_read_only_reflection_request(plan,
                scenario_id=scenario_id, observation_id=observation_id, **lineage(fixture))
        result.append(_REFLECTION_PARENTS[key])
    return tuple(result)


def rehashed(payload):
    result = deepcopy(payload)
    result.pop("authorization_fingerprint", None)
    result["authorization_fingerprint"] = sha256(json.dumps(result, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return result


def rows(authorization):
    return {row.scenario_id: row for row in authorization.scenarios}


def snapshot(case):
    fixture, plan, admission = case
    return tuple(record.to_json() for record in (
        fixture[0], fixture[1]["plan"], fixture[2], fixture[3], fixture[4], fixture[5],
        plan, admission)) + (fixture[1]["current_source"],)


def test_BANK_without_runtime_source_preserves_frozen_negative_authority(bank):
    before = snapshot(bank)
    _, plan, admission = bank
    authorization = build(bank)
    assert authorization.status == "diagnostic_execution_authority_missing"
    assert authorization.policy_authorized is False
    assert authorization.diagnostic_runtime_policy_authorized is False
    assert authorization.runtime_executor_available is False
    assert authorization.execution_completed is False
    assert not authorization.authorized_scenario_ids
    assert not authorization.authorized_invocation_targets
    assert not authorization.authorized_observation_targets
    assert not admission.admitted_scenarios
    assert admission.evidence_authority.diagnostic_execution_permitted is False
    assert validate(authorization.as_dict(), bank) == authorization
    decisions = rows(authorization)
    for scenario in plan.scenarios:
        row = decisions[scenario.scenario_id]
        assert row.policy_authorized is False
        if scenario.purpose in CAPABLE_PURPOSES:
            assert row.capability_available is True
            assert "diagnostic_execution_authority_missing" in row.reasons
        else:
            assert scenario.purpose in INTEREST_PURPOSES
            assert row.capability_available is False
            assert "deterministic_console_input" in row.reasons
    assert snapshot(bank) == before


@pytest.mark.parametrize("source_kind", SOURCE_KINDS)
def test_synthetic_source_provenance_is_explicit_exact_and_never_real_consent(bank, source_kind):
    before = snapshot(bank)
    source = issue(bank, source_kind=source_kind)
    authorization = build(bank, source=source)
    assert source.as_dict()["source_kind"] == source_kind
    assert source.as_dict()["synthetic"] is True
    assert source.as_dict()["fixture_id"].startswith("synthetic")
    assert authorization.authorization_source_kind == source_kind
    assert authorization.authorization_source_fingerprint == source.fingerprint
    assert authorization.policy_authorized is True
    assert authorization.status == "authorized_but_executor_unavailable"
    assert authorization.runtime_executor_available is False
    assert authorization.execution_completed is False
    assert validate(authorization, bank, source=source) == authorization
    assert snapshot(bank) == before


def test_atomic_scope_binds_complete_scenario_invocations_observations_and_reflection(bank):
    fixture, plan, _ = bank
    source = issue(bank)
    authorization = build(bank, source=source)
    scenario = next(s for s in plan.scenarios if s.purpose == "successful_transfer")
    assert authorization.authorized_scenario_ids == (scenario.scenario_id,)
    assert authorization.authorized_scenarios == (scenario,)
    required_invocations = {scenario.constructor, scenario.invocation.target,
        *(call.target for call in scenario.setup_invocations)}
    assert set(authorization.authorized_invocation_targets) == required_invocations
    assert authorization.authorized_observation_targets == scenario.observations
    expected_reflection = tuple(reflection.build_read_only_reflection_request(plan,
        scenario_id=scenario.scenario_id, observation_id=observation.observation_id,
        **lineage(fixture)) for observation in scenario.observations
        if observation.mechanism == "read_only_reflection")
    assert authorization.authorized_reflection_requests == expected_reflection
    assert expected_reflection
    assert all(request.operation == "read_exact_bound_field" for request in expected_reflection)
    assert {request.target.name for request in expected_reflection} == {"balance", "savingBalance"}
    assert "read_only_reflection" in authorization.authorized_diagnostic_capability_classes
    assert "deterministic_console_input" not in authorization.authorized_diagnostic_capability_classes
    decisions = rows(authorization)
    assert decisions[scenario.scenario_id].policy_authorized is True
    assert all(not row.policy_authorized for key, row in decisions.items() if key != scenario.scenario_id)


def test_direct_only_capability_remains_unauthorized_until_typed_source(cases):
    case = cases["direct"]
    absent = build(case, reflection_descriptor=None)
    assert absent.policy_authorized is False
    assert absent.status == "diagnostic_execution_authority_missing"
    assert all(row.capability_available and not row.policy_authorized for row in absent.scenarios)
    source = issue(case)
    authorized = build(case, source=source, reflection_descriptor=None)
    assert authorized.policy_authorized is True
    assert authorized.status == "authorized_but_executor_unavailable"
    assert authorized.reflection_capability_available is False
    assert not authorized.authorized_reflection_requests
    assert validate(authorized, case, source=source, reflection_descriptor=None) == authorized


@pytest.mark.parametrize("purpose", sorted(INTEREST_PURPOSES))
def test_interest_source_cannot_authorize_or_supply_console(bank, purpose):
    source = issue(bank, purposes=(purpose,))
    authorization = build(bank, source=source)
    scenario = next(s for s in bank[1].scenarios if s.purpose == purpose)
    decision = rows(authorization)[scenario.scenario_id]
    assert decision.policy_authorized is True
    assert decision.capability_available is False
    assert decision.status == "blocked_missing_capability"
    assert "deterministic_console_input" in decision.reasons
    assert authorization.status == "blocked_missing_capability"
    assert authorization.console_capability_available is False
    assert authorization.console_authorized is False
    assert authorization.runtime_executor_available is False
    assert "deterministic_console_input" not in authorization.authorized_diagnostic_capability_classes
    assert validate(authorization, bank, source=source) == authorization


def test_missing_reflection_stays_independent_of_policy_authority(bank):
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        issue(bank, reflection_descriptor=None, reflection_requests=())
    assert rejected.value.code == "authorization_scope_mismatch"
    authorization = build(bank, behavioral_admission=None, reflection_descriptor=None,
        reflection_requests=())
    assert authorization.policy_authorized is False
    assert authorization.reflection_capability_available is False
    assert any("read_only_reflection" in row.reasons for row in authorization.scenarios
        if row.scenario.purpose in CAPABLE_PURPOSES)


def test_exact_reflection_parents_can_bind_policy_while_capability_is_absent(bank):
    source = issue(bank, reflection_descriptor=None)
    authorization = build(bank, source=source, behavioral_admission=None, reflection_descriptor=None)
    assert authorization.policy_authorized is True
    assert authorization.reflection_capability_available is False
    assert authorization.status == "blocked_missing_capability"
    assert authorization.authorized_reflection_requests
    assert any("read_only_reflection" in row.reasons for row in authorization.scenarios
        if row.policy_authorized)
    assert validate(authorization, bank, source=source, behavioral_admission=None,
        reflection_descriptor=None) == authorization


@pytest.mark.parametrize("field,value", (
    ("execution_authorized", True), ("mutation", True), ("method_invocation", True),
    ("enumeration", True), ("operation", "write_field"), ("availability", "authorized"),
))
def test_forged_reflection_descriptor_cannot_turn_capability_into_authority(bank, field, value):
    forged = deepcopy(reflection.get_read_only_reflection_capability_descriptor())
    object.__setattr__(forged, field, value)
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        build(bank, source=issue(bank), reflection_descriptor=forged)
    assert rejected.value.code in {"authorization_invalid", "authorization_authority_escalation"}


def test_serialized_reflection_descriptor_is_not_trusted(bank):
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        build(bank, source=issue(bank),
            reflection_descriptor=reflection.get_read_only_reflection_capability_descriptor().as_dict())
    assert rejected.value.code == "authorization_invalid"


@pytest.mark.parametrize("claimed_kind", SOURCE_KINDS)
def test_caller_JSON_approval_is_never_an_authenticated_source(bank, claimed_kind):
    forged = issue(bank, source_kind=claimed_kind).as_dict()
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        build(bank, source=forged)
    assert rejected.value.code == "authorization_source_invalid"


def test_synthetic_source_requires_fixture_identity_and_known_source_kind(bank):
    for changes in ({"fixture_id": "real-BANK2-approval"},
            {"source_kind": "user_probably_wanted_tests"}):
        with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
            issue(bank, **changes)
        assert rejected.value.code in {"authorization_invalid", "authorization_source_invalid"}


def test_typed_source_constructor_bypass_and_replacement_are_rejected(bank):
    original = issue(bank)
    for forged in (replace(original, fixture_id="synthetic-tampered"), deepcopy(original)):
        if forged.fixture_id == original.fixture_id:
            object.__setattr__(forged.scope, "scenario_ids", ("BANK.unplanned",))
        with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
            build(bank, source=forged)
        assert rejected.value.code == "authorization_source_invalid"


def test_unsigned_typed_fixture_source_does_not_establish_authority(bank):
    unsigned = replace(issue(bank), _signature="")
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        build(bank, source=unsigned)
    assert rejected.value.code == "authorization_source_invalid"


@pytest.mark.parametrize("selection", (("BANK.*",), ("all tests",), ("BANK.unplanned",), ()))
def test_unplanned_wildcard_or_empty_source_selection_is_rejected(bank, selection):
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        issue(bank, scenario_ids=selection)
    assert rejected.value.code in {"authorization_scope_mismatch", "authorization_invalid"}


@pytest.mark.parametrize("part", (
    "extra_scenario", "extra_invocation", "extra_observation", "extra_reflection",
    "half_observation", "half_constructor", "half_scenario", "fixture_value",
))
def test_rehashed_authorization_cannot_expand_or_reduce_complete_scope(bank, part):
    source = issue(bank)
    authorization = build(bank, source=source)
    payload = authorization.as_dict()
    if part == "extra_scenario":
        payload["authorized_scenario_ids"].append("BANK.unplanned")
    elif part == "extra_invocation":
        extra = deepcopy(payload["authorized_invocation_targets"][0])
        extra["name"] = "unplannedProductMethod"
        payload["authorized_invocation_targets"].append(extra)
    elif part == "extra_observation":
        extra = deepcopy(payload["authorized_observation_targets"][0])
        extra["observation_id"] = "unplanned_debug_field"
        extra["target"]["name"] = "password"
        payload["authorized_observation_targets"].append(extra)
    elif part == "extra_reflection":
        payload["authorized_reflection_requests"][0]["target"]["name"] = "password"
    elif part == "half_observation":
        payload["authorized_observation_targets"].pop()
    elif part == "half_constructor":
        payload["authorized_invocation_targets"] = [target for target in
            payload["authorized_invocation_targets"] if target["kind"] != "constructor"]
    elif part == "half_scenario":
        payload["authorized_scenarios"][0]["observations"].pop()
    else:
        argument = next(a for a in payload["authorized_scenarios"][0]["invocation"]["arguments"]
            if a["declared_type"] == "double")
        argument["value"] = 123456.0
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        validate(rehashed(payload), bank, source=source)
    assert rejected.value.code == "authorization_scope_mismatch"


def test_atomic_interest_scope_cannot_omit_required_setup(bank):
    source = issue(bank, purposes=("savings_interest",))
    payload = build(bank, source=source).as_dict()
    assert payload["authorized_scenarios"][0]["setup_invocations"]
    payload["authorized_scenarios"][0]["setup_invocations"].pop()
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        validate(rehashed(payload), bank, source=source)
    assert rejected.value.code == "authorization_scope_mismatch"


@pytest.mark.parametrize("missing", ("all", "one"))
def test_authorization_cannot_create_missing_interest_REFLECT_parent_requests(bank, missing):
    fixture, plan, admission = bank
    identifier = next(s.scenario_id for s in plan.scenarios if s.purpose == "savings_interest")
    requests = external_reflection_parents(bank, scenario_ids=(identifier,))
    assert requests
    supplied = () if missing == "all" else requests[:-1]
    with patch.object(reflection, "build_read_only_reflection_request",
            wraps=reflection.build_read_only_reflection_request) as builder, pytest.raises(
            owner.RuntimeDiagnosticAuthorizationError) as rejected:
        owner.issue_synthetic_runtime_authorization_source(plan, **lineage(fixture),
            behavioral_admission=admission, scenario_ids=(identifier,),
            fixture_id="synthetic-missing-interest-reflection-parents", reflection_requests=supplied)
    assert rejected.value.code == "authorization_scope_mismatch"
    # The frozen validator reconstructs each supplied parent. Authorization
    # must never request an observation absent from those supplied parents.
    reconstructed = {call.kwargs.get("observation_id") for call in builder.call_args_list
        if call.kwargs.get("scenario_id") == identifier}
    assert reconstructed == {request.observation_id for request in supplied}


@pytest.mark.parametrize("purpose", ("deployment", "product_operation", "arbitrary_program_execution"))
def test_exact_diagnostic_evidence_purpose_cannot_be_reinterpreted(bank, purpose):
    source = issue(bank)
    payload = build(bank, source=source).as_dict()
    payload["purpose"] = purpose
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        validate(rehashed(payload), bank, source=source)
    assert rejected.value.code == "authorization_scope_mismatch"


@pytest.mark.parametrize("prohibition", (
    "repository_source_writes_forbidden", "product_state_persistence_forbidden",
    "network_use_forbidden", "process_spawning_beyond_fixed_runtime_adapter_forbidden",
    "arbitrary_filesystem_effects_forbidden", "arbitrary_environment_inspection_forbidden",
    "arbitrary_shell_forbidden", "reflection_writes_forbidden",
    "private_method_invocation_forbidden", "field_enumeration_forbidden",
    "console_authorization_forbidden",
))
def test_mandatory_effect_prohibition_cannot_be_removed(bank, prohibition):
    source = issue(bank)
    payload = build(bank, source=source).as_dict()
    payload["effect_boundaries"][prohibition] = False
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        validate(rehashed(payload), bank, source=source)
    assert rejected.value.code == "authorization_authority_escalation"


@pytest.mark.parametrize("field", FALSE_AUTHORITIES + (
    "runtime_executor_available", "execution_completed", "network_authorized",
    "repository_write", "product_write", "reflection_write", "test_write", "apply",
    "private_method_invocation_authority", "field_enumeration_authority",
))
def test_false_authorities_and_unavailable_execution_cannot_be_escalated(bank, field):
    source = issue(bank)
    authorization = build(bank, source=source)
    for nested in (False, True):
        payload = authorization.as_dict()
        (payload["scenarios"][0] if nested else payload)[field] = True
        with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
            validate(rehashed(payload), bank, source=source)
        assert rejected.value.code == "authorization_authority_escalation"


@pytest.mark.parametrize("field,value", (
    ("shell_command", "java SavingAccount"), ("java_command", ["java", "SavingAccount"]),
    ("javac_command", ["javac", "SavingAccount.java"]), ("command", "cmd.exe"),
    ("powershell", "Write-Output arbitrary"), ("bash", "echo arbitrary"),
    ("java_source", "class DiagnosticHarness {}"), ("junit_source", "class BehaviorTest {}"),
    ("test_file", "BehaviorTest.java"), ("getDeclaredFields", True),
))
def test_command_harness_test_or_enumeration_payload_is_forbidden(bank, field, value):
    source = issue(bank)
    authorization = build(bank, source=source)
    payload = authorization.as_dict()
    payload[field] = value
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        validate(rehashed(payload), bank, source=source)
    assert rejected.value.code in {"authorization_invalid", "authorization_authority_escalation"}


@pytest.mark.parametrize("part", (
    "task", "repository", "candidate", "materialization", "compile", "specification",
    "execution_plan", "source_bytes", "authorization_source", "admission",
))
def test_structural_freshness_invalidates_changed_lineage(cases, bank, part):
    fixture, _, _ = bank
    other_fixture, other_plan, other_admission = cases["nested"]
    source = issue(bank)
    authorization = build(bank, source=source)
    changes = {}
    if part == "task":
        changes["task_contract"] = understand_request(fixture[1]["task_contract"].raw_request.text + "\nchanged")
    elif part == "repository":
        changes["repository_id"] = "different-" + "b" * 32
    elif part == "candidate":
        changes["candidate"] = other_fixture[2]
    elif part == "materialization":
        changes["materialized"] = other_fixture[3]
    elif part == "compile":
        changes["compile_receipt"] = other_fixture[4]
    elif part == "specification":
        changes["specification"] = other_fixture[5]
    elif part == "execution_plan":
        changes["execution_plan"] = other_plan
    elif part == "source_bytes":
        changes["current_source"] = fixture[1]["current_source"] + b"\n// changed"
    elif part == "authorization_source":
        source = issue(bank, fixture_id="synthetic-changed-trusted-source")
    else:
        changes["behavioral_admission"] = other_admission
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        validate(authorization, bank, source=source, **changes)
    assert rejected.value.code == "authorization_stale"


def test_capability_descriptor_freshness_does_not_mutate_prior_authorization(bank):
    source = issue(bank)
    authorization = build(bank, source=source)
    before = authorization.to_json()
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError) as rejected:
        validate(authorization, bank, source=source, reflection_descriptor=None)
    assert rejected.value.code == "authorization_stale"
    assert authorization.to_json() == before


def test_validator_reconstructs_frozen_plan_admission_and_reflection(bank):
    source = issue(bank)
    authorization = build(bank, source=source)
    with patch.object(planner, "validate_behavioral_evidence_execution_plan",
            wraps=planner.validate_behavioral_evidence_execution_plan) as plan_gate, patch.object(
            admission_owner, "validate_behavioral_execution_admission",
            wraps=admission_owner.validate_behavioral_execution_admission) as admission_gate, patch.object(
            reflection, "validate_read_only_reflection_capability_descriptor",
            wraps=reflection.validate_read_only_reflection_capability_descriptor) as reflection_gate:
        assert validate(authorization.as_dict(), bank, source=source) == authorization
    assert plan_gate.call_count >= 1
    assert admission_gate.call_count >= 1
    assert reflection_gate.call_count >= 1


def test_authorization_is_immutable_deterministic_and_timings_are_external(bank):
    source = issue(bank)
    timings = [{}, {}]
    repeated = [build(bank, source=source, timings=sample) for sample in timings]
    assert repeated[0] == repeated[1]
    assert repeated[0].fingerprint == repeated[1].fingerprint
    assert json.loads(repeated[0].to_json()) == repeated[0].as_dict()
    assert all(set(sample) == set(owner.TIMING_FIELDS) for sample in timings)
    assert all(type(value) is float and value >= 0 for sample in timings for value in sample.values())
    assert "timings" not in repeated[0].as_dict()
    with pytest.raises(FrozenInstanceError):
        repeated[0].status = "execution_ready"
    with pytest.raises(FrozenInstanceError):
        source.fixture_id = "synthetic-mutated"
    with pytest.raises(owner.RuntimeDiagnosticAuthorizationError):
        replace(repeated[0], authorized_scenario_ids=list(repeated[0].authorized_scenario_ids))


def test_effect_matrix_zero_effects_and_policy_is_not_enforcement(bank):
    source = issue(bank)
    payload = build(bank, source=source).as_dict()
    assert payload["authority"] == "bounded_runtime_diagnostic_only"
    assert all(payload[field] is False for field in FALSE_AUTHORITIES)
    for field in ("java_execution_count", "reflection_execution_count", "console_open_count",
            "javac_calls", "diagnostic_harness_generation_count", "test_generation_count",
            "model_calls", "author_calls", "repository_traversals", "source_mutation"):
        assert payload[field] == 0
    assert payload["runtime_executor_available"] is False
    assert payload["execution_completed"] is False
    assert payload["effect_boundaries"]["network_use_forbidden"] is True
    assert payload["effect_boundaries"]["enforcement_available"] is False


def test_effect_guard_denies_process_render_receipt_console_traversal_and_write(deny_entire_focused_suite):
    import os
    import subprocess
    import core.read_only_reflection_java as adapter
    operations = (
        lambda: subprocess.run(["java", "NeverLaunched"]),
        lambda: os.system("javac NeverCompiled.java"),
        lambda: os.popen("cmd.exe"),
        lambda: input("Never opened console"),
        lambda: open("CONIN$", "r"),
        lambda: adapter.render_read_only_reflection_adapter(None),
        lambda: reflection._issue_adapter_observation(None),
        lambda: os.listdir("."),
        lambda: Path("NeverCreated.java").write_text("class NeverCreated {}"),
    )
    for operation in operations:
        with pytest.raises(AssertionError, match="PREFLIGHT.RUNTIME.1 effect denied"):
            operation()
    assert deny_entire_focused_suite.denied_attempts


def test_bookkeeping_reversal_preserves_frozen_receipts():
    from tests._preflight_runtime1_maintenance import before_preflight_runtime1
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tests/fixtures/preflight_runtime1_reversal.json").read_text(encoding="utf-8"))
    for record in receipt["reversals"]:
        content = (root / record["path"]).read_bytes()
        assert sha256(before_preflight_runtime1(record["path"], content)).hexdigest() == record["entry_sha256"]
        with pytest.raises(AssertionError):
            before_preflight_runtime1(record["path"], content + b"\n")
