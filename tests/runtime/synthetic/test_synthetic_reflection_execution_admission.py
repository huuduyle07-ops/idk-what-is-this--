"""SYNTH.REFLECT.ADMIT.1 proves exact admission and never executes reflection."""
from contextlib import contextmanager
import copy
import dataclasses
import json

import pytest

from core.runtime.synthetic import synthetic_read_only_reflection as reflection
from core.runtime.synthetic import synthetic_reflection_execution_admission as admission_owner
from core.runtime.synthetic import synthetic_runtime_authorization as authorization
from tests._preflight_runtime1_guard import no_runtime_effects


ROLE_FACTORIES = (
    (admission_owner.BEFORE_ROLE, reflection.executor1r_before_request),
    (admission_owner.AFTER_ROLE, reflection.executor1r_after_request),
)
FALSE_AUTHORITY_FIELDS = (
    "runtime_authority", "real_task_runtime_authority", "repository_write_authority",
    "apply_authority", "field_write_authority", "enumeration_authority",
    "private_method_authority", "constructor_reflection_authority",
    "arbitrary_class_loading_authority",
)


@pytest.fixture(autouse=True)
def _deny_runtime_effects():
    with no_runtime_effects(strict=True) as evidence:
        yield evidence
    assert evidence.denied_attempts == {}


def _authorization():
    spec = authorization.executor1r_decrement_3_spec()
    return authorization.issue_synthetic_runtime_authorization(
        spec, source=authorization.get_executor1r_decrement_3_source())


def _pair(role):
    factory = dict(ROLE_FACTORIES)[role]
    auth = _authorization()
    request = factory()
    admission = admission_owner.issue_synthetic_reflection_execution_admission(auth, request)
    return auth, request, admission


@contextmanager
def _temporarily_set(value, name, changed):
    original = getattr(value, name)
    object.__setattr__(value, name, changed)
    try:
        yield
    finally:
        object.__setattr__(value, name, original)


def _different(value):
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return value + "_changed"
    return object()


def _rejected(operation):
    with pytest.raises(ValueError):
        operation()


def test_verify_issues_exactly_two_authenticated_role_separated_admissions():
    admissions, report = admission_owner.verify()
    before, after = admissions
    assert report["status"] == "SYNTH_REFLECT_ADMIT_1_COMPLETE"
    assert report["supported_synthetic_reflection_admission_count"] == 2
    assert [before.observation_role, after.observation_role] == list(admission_owner.SUPPORTED_ROLES)
    assert admission_owner.validate_synthetic_reflection_execution_admission(before) is before
    assert admission_owner.validate_synthetic_reflection_execution_admission(after) is after
    assert before.admission_id != after.admission_id
    assert before.synthetic_authorization_issuance_id != after.synthetic_authorization_issuance_id
    assert before.reflection_request_issuance_id != after.reflection_request_issuance_id
    assert before.renderer_fingerprint != after.renderer_fingerprint
    assert before.synthetic_reflection_execution_authority is True
    assert after.synthetic_reflection_execution_authority is True
    for admission in admissions:
        assert admission.consumption_state == "issued"
        assert admission.single_execution_use is True
        assert all(getattr(admission, field) is False for field in FALSE_AUTHORITY_FIELDS)
    assert report["role_separation_enforced"] is True
    assert report["synthetic_runtime_authorizations_consumed"] == 0
    assert report["reflection_admissions_consumed"] == 0
    assert report["source_projected"] is False
    assert report["measured_observations"] is None
    assert report["positive_runtime_receipt"] is None
    for key in ("java_compile_count", "jvm_execution_count", "reflection_execution_count",
            "containers_created", "docker_calls", "network_calls", "shell_calls", "child_processes"):
        assert report[key] == 0
    assert "expected_before" not in json.dumps(report)
    assert "expected_after" not in json.dumps(report)


@pytest.mark.parametrize("role,factory", ROLE_FACTORIES)
def test_admission_binds_exact_target_upstream_identities_and_fixed_renderer(role, factory):
    auth = _authorization()
    request = factory()
    admission = admission_owner.issue_synthetic_reflection_execution_admission(auth, request)
    assert admission_owner.synthetic_reflection_admission_satisfies_executor(
        admission, auth, request) is True
    assert admission.scenario_phase_id == admission_owner.SCENARIO_PHASE_ID
    assert admission.scenario_id == admission_owner.SCENARIO_ID
    assert admission.source_sha256 == admission_owner.SOURCE_SHA256
    assert admission.definition_sha256 == admission_owner.DEFINITION_SHA256
    assert (admission.owner, admission.member, admission.declared_type, admission.operation) == (
        "SyntheticStateBox", "value", "int", "read_exact_bound_field")
    assert admission.renderer_identity == "SYNTH.REFLECT.1.render_synthetic_read_only_reflection"
    assert len(admission.renderer_fingerprint) == 64
    assert admission.synthetic_authorization_fingerprint == auth.fingerprint
    assert admission.synthetic_authorization_issuance_id == auth.issuance_id
    assert admission.reflection_request_fingerprint == request.fingerprint
    assert admission.reflection_request_issuance_id == request.issuance_id
    assert admission.observation_role == role == request.observation_role
    assert "_signature" not in json.dumps(admission.as_dict())


@pytest.mark.parametrize("role,factory", ROLE_FACTORIES)
def test_cross_role_reuse_and_role_reassignment_fail(role, factory):
    auth, request, admission = _pair(role)
    other_role = (admission_owner.AFTER_ROLE if role == admission_owner.BEFORE_ROLE
        else admission_owner.BEFORE_ROLE)
    other_request = dict(ROLE_FACTORIES)[other_role]()
    other_auth = _authorization()
    assert admission_owner.synthetic_reflection_admission_satisfies_executor(
        admission, other_auth, other_request) is False
    assert admission_owner.synthetic_reflection_admission_satisfies_executor(
        admission, auth, other_request) is False
    with _temporarily_set(request, "observation_role", other_role):
        assert admission_owner.synthetic_reflection_admission_satisfies_executor(
            admission, auth, request) is False
        _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(auth, request))
    with _temporarily_set(admission, "observation_role", other_role):
        _rejected(lambda: admission_owner.validate_synthetic_reflection_execution_admission(admission))


@pytest.mark.parametrize("clone_kind", ("copy", "deepcopy", "replace", "constructor", "dict", "json"))
def test_equal_or_exported_authorization_cannot_issue_admission(clone_kind):
    auth, request, _ = _pair(admission_owner.BEFORE_ROLE)
    if clone_kind == "copy":
        clone = copy.copy(auth)
    elif clone_kind == "deepcopy":
        clone = copy.deepcopy(auth)
    elif clone_kind == "replace":
        clone = dataclasses.replace(auth)
    elif clone_kind == "constructor":
        clone = type(auth)(**{f.name: getattr(auth, f.name)
            for f in dataclasses.fields(auth) if f.init})
    elif clone_kind == "dict":
        clone = auth.as_dict()
    else:
        clone = json.loads(json.dumps(auth.as_dict()))
    assert clone is not auth
    _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(clone, request))


@pytest.mark.parametrize("clone_kind", ("copy", "deepcopy", "replace", "dict", "json"))
def test_equal_or_exported_reflection_request_cannot_issue_admission(clone_kind):
    auth, request, _ = _pair(admission_owner.BEFORE_ROLE)
    if clone_kind == "copy":
        clone = copy.copy(request)
    elif clone_kind == "deepcopy":
        clone = copy.deepcopy(request)
    elif clone_kind == "replace":
        clone = dataclasses.replace(request)
    elif clone_kind == "dict":
        clone = request.as_dict()
    else:
        clone = json.loads(json.dumps(request.as_dict()))
    assert clone is not request
    _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(auth, clone))


@pytest.mark.parametrize("clone_kind", ("copy", "deepcopy", "replace", "constructor", "dict", "json"))
def test_admission_copy_dataclass_replace_and_report_reconstruction_fail(clone_kind):
    auth, request, admission = _pair(admission_owner.BEFORE_ROLE)
    if clone_kind == "copy":
        clone = copy.copy(admission)
    elif clone_kind == "deepcopy":
        clone = copy.deepcopy(admission)
    elif clone_kind == "replace":
        clone = dataclasses.replace(admission)
    elif clone_kind == "constructor":
        clone = type(admission)(**{f.name: getattr(admission, f.name)
            for f in dataclasses.fields(admission) if f.init})
    elif clone_kind == "dict":
        clone = admission.as_dict()
    else:
        clone = json.loads(json.dumps(admission.as_dict()))
    assert clone is not admission
    _rejected(lambda: admission_owner.validate_synthetic_reflection_execution_admission(clone))
    assert admission_owner.synthetic_reflection_admission_satisfies_executor(
        clone, auth, request) is False


@pytest.mark.parametrize("field", (
    "scenario_phase_id", "scenario_id", "source_sha256", "definition_sha256", "owner",
    "member", "declared_type", "operation", "renderer_identity", "renderer_fingerprint",
    "synthetic_authorization_fingerprint", "synthetic_authorization_issuance_id",
    "reflection_request_fingerprint", "reflection_request_issuance_id", "admission_id",
    "issuing_process_id", "synthetic_reflection_execution_authority", "runtime_authority",
    "real_task_runtime_authority", "repository_write_authority", "apply_authority",
    "field_write_authority", "enumeration_authority", "private_method_authority",
    "constructor_reflection_authority", "arbitrary_class_loading_authority",
    "single_execution_use", "consumption_state", "_signature",
))
def test_every_admission_projection_field_is_authenticated(field):
    _, _, admission = _pair(admission_owner.BEFORE_ROLE)
    original = getattr(admission, field)
    changed = _different(original)
    with _temporarily_set(admission, field, changed):
        _rejected(lambda: admission_owner.validate_synthetic_reflection_execution_admission(admission))


@pytest.mark.parametrize("field,value", (
    ("phase_id", "SYNTH.REFLECT.1"),
    ("scenario_id", "other_scenario"),
    ("source_sha256", "0" * 64),
    ("definition_sha256", "0" * 64),
    ("owner", "BankAccount"),
    ("member", "balance"),
    ("declared_type", "double"),
    ("operation", "write_exact_bound_field"),
    ("observation_role", "direct_public_return"),
    ("source_kind", "BANK"),
))
def test_wrong_reflection_contract_fields_are_rejected(field, value):
    auth, request, _ = _pair(admission_owner.BEFORE_ROLE)
    with _temporarily_set(request, field, value):
        assert admission_owner.synthetic_reflection_admission_satisfies_executor(
            object(), auth, request) is False
        _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(auth, request))


@pytest.mark.parametrize("field", ("runtime_authority", "real_task_runtime_authority",
        "synthetic_runtime_authority", "reflection_authority", "execution_ready"))
def test_authority_widened_synth_auth_is_rejected(field):
    auth, request, _ = _pair(admission_owner.BEFORE_ROLE)
    with _temporarily_set(auth, field, _different(getattr(auth, field))):
        assert admission_owner.synthetic_reflection_admission_satisfies_executor(
            object(), auth, request) is False
        _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(auth, request))


def test_public_invocation_and_complete_observation_contract_are_required():
    spec = authorization.executor1r_decrement_3_spec()
    auth, request, _ = _pair(admission_owner.BEFORE_ROLE)
    invocation = spec.invocation_contract
    with _temporarily_set(invocation, "public_method", "other_method"):
        assert admission_owner.synthetic_reflection_admission_satisfies_executor(
            object(), auth, request) is False
        _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(auth, request))
    with _temporarily_set(spec.observation_contract, "roles", ("direct_public_return",)):
        assert admission_owner.synthetic_reflection_admission_satisfies_executor(
            object(), auth, request) is False
        _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(auth, request))


def test_bank_historical_authorization_and_historical_reflection_request_are_rejected():
    auth, request, _ = _pair(admission_owner.BEFORE_ROLE)
    from scripts import replay_preflight_runtime1 as bank_replay
    fixture = bank_replay.planning_fixture("preserve_base_compatibility", source=bank_replay.BANK)
    plan = bank_replay.build_plan(fixture)
    bank_authorization = bank_replay.build(fixture, plan)
    assert admission_owner.synthetic_reflection_admission_satisfies_executor(
        object(), bank_authorization, request) is False
    _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(bank_authorization, request))

    from core import read_only_reflection as historical_reflection
    from scripts.replay_patch_candidate_behavior_reflect1 import reflection_inputs
    historic_inputs = reflection_inputs(fixture, plan)
    scenario = next(item for item in plan.scenarios
        if any(observation.mechanism == "read_only_reflection" for observation in item.observations))
    observation = next(item for item in scenario.observations
        if item.mechanism == "read_only_reflection")
    historical_request = historical_reflection.build_read_only_reflection_request(
        **historic_inputs, scenario_id=scenario.scenario_id,
        observation_id=observation.observation_id)
    assert type(historical_request) is historical_reflection.ReadOnlyReflectionRequest
    assert admission_owner.synthetic_reflection_admission_satisfies_executor(
        object(), auth, historical_request) is False
    _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(auth, historical_request))


def test_process_change_or_admission_key_change_rejects_existing_handle(monkeypatch):
    auth, request, admission = _pair(admission_owner.BEFORE_ROLE)
    monkeypatch.setattr(admission_owner.os, "getpid", lambda: admission.issuing_process_id + 1)
    _rejected(lambda: admission_owner.validate_synthetic_reflection_execution_admission(admission))
    assert admission_owner.synthetic_reflection_admission_satisfies_executor(
        admission, auth, request) is False
    monkeypatch.undo()
    monkeypatch.setattr(admission_owner, "_SECRET", b"different-admission-process-key".ljust(32, b"!"))
    _rejected(lambda: admission_owner.validate_synthetic_reflection_execution_admission(admission))


def test_uninitialized_foreign_and_report_only_values_never_authenticate():
    for value in (None, {}, {"phase_id": "PREFLIGHT.RUNTIME.1"}, object()):
        _rejected(lambda value=value:
            admission_owner.validate_synthetic_reflection_execution_admission(value))
    uninitialized = object.__new__(admission_owner.SyntheticReflectionExecutionAdmission)
    _rejected(lambda: admission_owner.validate_synthetic_reflection_execution_admission(uninitialized))


def test_compatibility_predicate_is_pure_repeatable_and_does_not_consume():
    auth, request, admission = _pair(admission_owner.AFTER_ROLE)
    auth_before = auth.as_dict()
    request_before = request.as_dict()
    admission_before = admission.as_dict()
    for _ in range(3):
        assert admission_owner.synthetic_reflection_admission_satisfies_executor(
            admission, auth, request) is True
    assert auth.as_dict() == auth_before
    assert request.as_dict() == request_before
    assert admission.as_dict() == admission_before
    assert auth.synthetic_runtime_authorizations_consumed == 0
    assert admission.consumption_state == "issued"


def test_public_issue_api_accepts_no_role_or_renderer_source_override():
    auth, request, _ = _pair(admission_owner.BEFORE_ROLE)
    with pytest.raises(TypeError):
        admission_owner.issue_synthetic_reflection_execution_admission(
            auth, request, observation_role=admission_owner.AFTER_ROLE)
    with pytest.raises(TypeError):
        admission_owner.issue_synthetic_reflection_execution_admission(
            auth, request, java_source="caller-controlled")


@pytest.mark.parametrize("operation", (
    "write_exact_bound_field", "enumerate_fields", "read_private_method",
    "reflect_constructor", "load_arbitrary_class", "getDeclaredFields",
))
def test_every_non_read_operation_is_rejected(operation):
    auth, request, _ = _pair(admission_owner.BEFORE_ROLE)
    with _temporarily_set(request, "operation", operation):
        assert admission_owner.synthetic_reflection_admission_satisfies_executor(
            object(), auth, request) is False
        _rejected(lambda: admission_owner.issue_synthetic_reflection_execution_admission(auth, request))


def test_admission_hmac_domain_is_separate_from_both_upstream_owners(monkeypatch):
    auth, request, admission = _pair(admission_owner.BEFORE_ROLE)
    assert admission_owner._SECRET != authorization._SECRET
    assert admission_owner._SECRET != reflection._SECRET
    assert authorization._SECRET != reflection._SECRET
    monkeypatch.setattr(admission_owner, "_SECRET", authorization._SECRET)
    _rejected(lambda: admission_owner.validate_synthetic_reflection_execution_admission(admission))
