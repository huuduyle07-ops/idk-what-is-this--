"""SYNTH.AUTH.1: exact, process-local authority without runtime execution."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from contextlib import contextmanager

import pytest

from core.runtime.synthetic import synthetic_runtime_authorization as synth
from tests._preflight_runtime1_guard import no_runtime_effects


SPEC = synth.executor1r_decrement_3_spec()
SOURCE = synth.get_executor1r_decrement_3_source()
SPEC_FIELDS = tuple(field.name for field in dataclasses.fields(SPEC))
AUTH_FIELDS = tuple(field.name for field in dataclasses.fields(synth.SyntheticRuntimeAuthorization))


class _StringSubclass(str):
    pass


class _BytesSubclass(bytes):
    pass


def _different(value):
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return value + "_tampered"
    if type(value) is bytes:
        return value + b"_tampered"
    if type(value) is tuple:
        return value + ("unexpected",)
    if dataclasses.is_dataclass(value):
        field = dataclasses.fields(value)[0].name
        return dataclasses.replace(value, **{field: _different(getattr(value, field))})
    return object()


@contextmanager
def _temporarily_set(obj, field, value):
    original = getattr(obj, field)
    object.__setattr__(obj, field, value)
    try:
        yield
    finally:
        object.__setattr__(obj, field, original)


def _assert_rejected(operation):
    with pytest.raises(synth.SyntheticRuntimeAuthorizationError) as caught:
        operation()
    assert isinstance(caught.value, ValueError)
    assert type(caught.value.code) is str
    assert caught.value.code


def _issue():
    return synth.issue_synthetic_runtime_authorization(SPEC, source=SOURCE)


def test_supported_scenario_has_exact_non_bank_contract():
    assert synth.PHASE_ID == "SYNTH.AUTH.1"
    assert synth.executor1r_decrement_3_spec() is SPEC
    assert synth.validate_synthetic_runtime_scenario_spec(SPEC) is SPEC
    assert SPEC.schema_version == synth.SCHEMA_VERSION
    assert SPEC.phase_id == "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R"
    assert SPEC.scenario_id == "synthetic.EXECUTOR.1R.decrement_3"
    assert type(SPEC.purpose) is str and SPEC.purpose
    assert type(SOURCE) is bytes
    assert len(SOURCE) == SPEC.source_size_bytes == synth.SOURCE_SIZE_BYTES
    assert hashlib.sha256(SOURCE).hexdigest() == SPEC.source_sha256
    assert SPEC.source_sha256 == "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
    assert SPEC.sandbox_profile_id == "runtime_sandbox_2_v1"
    assert SPEC.sandbox_policy_sha256 == synth.SANDBOX_POLICY_SHA256
    assert SPEC.java_profile_id == "RUNTIME.JAVA.1"
    assert SPEC.java_schema_version == "runtime_java_1_v1"
    invocation = SPEC.invocation_contract
    assert invocation.owner == "SyntheticStateBox"
    assert invocation.public_method == "decrement"
    assert invocation.arguments == (3,)
    assert invocation.argument_types == ("int",)
    assert invocation.return_type == "boolean"
    observation = SPEC.observation_contract
    assert observation.roles == (
        "exact_private_state_before",
        "direct_public_return",
        "exact_private_state_after",
    )
    assert observation.expected_before == 10
    assert observation.expected_return is True
    assert observation.expected_after == 7
    assert observation.future_exact_reflection_required is True
    assert observation.reflection_authority is False
    metadata = observation.requested_field_metadata
    assert metadata.owner == "SyntheticStateBox"
    assert metadata.member == "value"
    assert metadata.declared_type == "int"
    assert metadata.source_sha256 == SPEC.source_sha256
    assert type(metadata.definition_sha256) is str
    assert len(metadata.definition_sha256) == 64
    assert SPEC.allowed_runtime_operations == ("direct_public_invocation",)
    assert SPEC.source_kind == "phase_owned_synthetic_fixture"
    for field in (
        "console_required", "network_required", "repository_access_required",
        "real_task_source", "human_approval_required",
    ):
        assert getattr(SPEC, field) is False


@pytest.mark.parametrize("field", SPEC_FIELDS)
def test_every_spec_field_is_pinned_even_on_the_owned_object(field):
    with _temporarily_set(SPEC, field, _different(getattr(SPEC, field))):
        _assert_rejected(lambda: synth.validate_synthetic_runtime_scenario_spec(SPEC))
        _assert_rejected(lambda: _issue())
    assert synth.validate_synthetic_runtime_scenario_spec(SPEC) is SPEC


@pytest.mark.parametrize("contract", ("invocation_contract", "observation_contract"))
def test_every_nested_contract_field_is_pinned(contract):
    nested = getattr(SPEC, contract)
    for field in dataclasses.fields(nested):
        with _temporarily_set(nested, field.name, _different(getattr(nested, field.name))):
            _assert_rejected(lambda: synth.validate_synthetic_runtime_scenario_spec(SPEC))
            _assert_rejected(lambda: _issue())


def test_every_field_metadata_value_is_pinned_and_grants_no_reflection():
    metadata = SPEC.observation_contract.requested_field_metadata
    for field in dataclasses.fields(metadata):
        with _temporarily_set(metadata, field.name, _different(getattr(metadata, field.name))):
            _assert_rejected(lambda: synth.validate_synthetic_runtime_scenario_spec(SPEC))
    auth = _issue()
    assert auth.future_exact_reflection_required is True
    assert auth.reflection_authority is False
    assert auth.execution_ready is False


@pytest.mark.parametrize("clone_kind", ("constructor", "replace", "dictionary", "json"))
def test_matching_strings_cannot_construct_supported_scenario(clone_kind):
    if clone_kind == "constructor":
        clone = type(SPEC)(**{field: getattr(SPEC, field) for field in SPEC_FIELDS})
    elif clone_kind == "replace":
        clone = dataclasses.replace(SPEC)
    elif clone_kind == "dictionary":
        clone = dataclasses.asdict(SPEC)
    else:
        clone = json.loads(json.dumps(dataclasses.asdict(SPEC)))
    _assert_rejected(lambda: synth.validate_synthetic_runtime_scenario_spec(clone))
    _assert_rejected(lambda: synth.issue_synthetic_runtime_authorization(clone, source=SOURCE))


@pytest.mark.parametrize("extra", (
    {"argv": ("java", "SyntheticStateBox")},
    {"shell": "java SyntheticStateBox; echo unauthorized"},
    {"command": "powershell -Command Write-Output unauthorized"},
))
def test_contract_constructor_has_no_executable_text_extension(extra):
    with pytest.raises(TypeError):
        type(SPEC)(**{field: getattr(SPEC, field) for field in SPEC_FIELDS}, **extra)


@pytest.mark.parametrize("path,value", (
    (("phase_id",), _StringSubclass(SPEC.phase_id)),
    (("source_size_bytes",), True),
    (("console_required",), 0),
    (("human_approval_required",), 0),
    (("invocation_contract", "arguments"), (True,)),
    (("invocation_contract", "arguments"), (3.0,)),
    (("invocation_contract", "arguments"), [3]),
    (("invocation_contract", "arguments"), ("3; echo unauthorized",)),
    (("invocation_contract", "public_method"), _StringSubclass("decrement")),
    (("observation_contract", "expected_before"), True),
    (("observation_contract", "expected_return"), 1),
    (("observation_contract", "expected_after"), 7.0),
    (("observation_contract", "future_exact_reflection_required"), 1),
    (("observation_contract", "reflection_authority"), 0),
))
def test_recursive_types_reject_python_equality_aliases(path, value):
    obj = SPEC
    for name in path[:-1]:
        obj = getattr(obj, name)
    with _temporarily_set(obj, path[-1], value):
        _assert_rejected(lambda: synth.validate_synthetic_runtime_scenario_spec(SPEC))
        _assert_rejected(lambda: _issue())


def test_contract_and_nested_metadata_are_immutable():
    objects = (
        SPEC, SPEC.invocation_contract, SPEC.observation_contract,
        SPEC.observation_contract.requested_field_metadata,
    )
    for obj in objects:
        field = dataclasses.fields(obj)[0].name
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(obj, field, _different(getattr(obj, field)))
    with pytest.raises(TypeError):
        SPEC.invocation_contract.arguments[0] = 4
    with pytest.raises(TypeError):
        SPEC.observation_contract.roles[0] = "reflection"


def test_issue_and_validate_exact_process_local_authorization():
    auth = _issue()
    assert synth.validate_synthetic_runtime_authorization(auth, spec=SPEC, source=SOURCE) is auth
    assert auth.schema_version == synth.AUTHORIZATION_SCHEMA_VERSION
    assert auth.issuer_phase_id == "SYNTH.AUTH.1"
    assert auth.scenario_phase_id == SPEC.phase_id
    assert auth.scenario_id == SPEC.scenario_id
    assert auth.source_sha256 == SPEC.source_sha256
    assert auth.source_size_bytes == SPEC.source_size_bytes
    assert auth.sandbox_profile_id == SPEC.sandbox_profile_id
    assert auth.sandbox_policy_sha256 == SPEC.sandbox_policy_sha256
    assert auth.java_profile_id == SPEC.java_profile_id
    assert auth.java_schema_version == SPEC.java_schema_version
    assert auth.source_kind == SPEC.source_kind
    assert auth.allowed_runtime_operations == ("direct_public_invocation",)
    assert auth.synthetic_runtime_authority is True
    for field in (
        "runtime_authority", "real_task_runtime_authority", "real_human_approval",
        "real_session_consumed", "reflection_authority", "execution_ready",
        "execution_completed", "repository_write_authority", "apply_authority",
        "network_authority", "console_authority",
    ):
        assert getattr(auth, field) is False
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        auth.runtime_authority = True


def test_each_issuance_has_independent_authenticated_identity():
    first = _issue()
    second = _issue()
    assert first is not second
    assert first.issuance_id != second.issuance_id
    assert len(first.issuance_id) == len(second.issuance_id) == 64
    assert synth.validate_synthetic_runtime_authorization(first, spec=SPEC, source=SOURCE) is first
    assert synth.validate_synthetic_runtime_authorization(second, spec=SPEC, source=SOURCE) is second


@pytest.mark.parametrize("field", AUTH_FIELDS)
def test_every_authorization_field_is_authenticated(field):
    auth = _issue()
    with _temporarily_set(auth, field, _different(getattr(auth, field))):
        _assert_rejected(
            lambda: synth.validate_synthetic_runtime_authorization(auth, spec=SPEC, source=SOURCE)
        )
    assert synth.validate_synthetic_runtime_authorization(auth, spec=SPEC, source=SOURCE) is auth


@pytest.mark.parametrize("clone_kind", ("constructor", "replace", "dictionary", "json"))
def test_authorization_clones_and_reports_cannot_be_replayed(clone_kind):
    auth = _issue()
    if clone_kind == "constructor":
        clone = type(auth)(**{
            field.name: getattr(auth, field.name)
            for field in dataclasses.fields(auth) if field.init
        })
    elif clone_kind == "replace":
        clone = dataclasses.replace(auth)
    elif clone_kind == "dictionary":
        clone = auth.as_dict()
    else:
        clone = json.loads(json.dumps(auth.as_dict()))
    _assert_rejected(lambda: synth.validate_synthetic_runtime_authorization(clone, spec=SPEC, source=SOURCE))


def test_report_has_no_authentication_proof_or_reissuance_capability():
    auth = _issue()
    report = auth.as_dict()
    assert report["report_only"] is True
    assert report["synthetic_runtime_authority"] is True
    assert report["runtime_authority"] is False
    assert report["reflection_authority"] is False
    assert report["execution_completed"] is False
    assert "_signature" not in report
    assert not any("secret" in name or "proof" in name for name in report)
    assert type(report["authorization_fingerprint"]) is str
    assert len(report["authorization_fingerprint"]) == 64
    _assert_rejected(lambda: synth.validate_synthetic_runtime_authorization(report, spec=SPEC, source=SOURCE))


def test_empty_authentication_signature_cannot_validate():
    auth = _issue()
    with _temporarily_set(auth, "_signature", ""):
        _assert_rejected(lambda: synth.validate_synthetic_runtime_authorization(auth, spec=SPEC, source=SOURCE))


@pytest.mark.parametrize("field,value", (
    ("synthetic_runtime_authority", 1),
    ("runtime_authority", 0),
    ("future_exact_reflection_required", 1),
    ("compile_count", False),
    ("source_size_bytes", float(len(SOURCE))),
    ("allowed_runtime_operations", ["direct_public_invocation"]),
    ("scenario_id", _StringSubclass(SPEC.scenario_id)),
))
def test_authorization_rejects_equal_values_with_foreign_types(field, value):
    auth = _issue()
    with _temporarily_set(auth, field, value):
        _assert_rejected(lambda: synth.validate_synthetic_runtime_authorization(auth, spec=SPEC, source=SOURCE))


@pytest.mark.parametrize("bad_source", (
    b"", SOURCE + b"\n", SOURCE[:-1],
    bytes([SOURCE[0] ^ 1]) + SOURCE[1:],
    SOURCE.decode("utf-8"), bytearray(SOURCE), memoryview(SOURCE), _BytesSubclass(SOURCE), None,
))
def test_wrong_source_bytes_types_digest_and_length_rejected(bad_source):
    auth = _issue()
    _assert_rejected(lambda: synth.issue_synthetic_runtime_authorization(SPEC, source=bad_source))
    _assert_rejected(
        lambda: synth.validate_synthetic_runtime_authorization(auth, spec=SPEC, source=bad_source)
    )


def test_authorization_is_bound_to_owned_spec_identity():
    auth = _issue()
    _assert_rejected(
        lambda: synth.validate_synthetic_runtime_authorization(auth, spec=dataclasses.replace(SPEC), source=SOURCE)
    )


def test_another_process_secret_cannot_authenticate_issued_authorization(monkeypatch):
    auth = _issue()
    monkeypatch.setattr(synth, "_SECRET", b"different-process-secret".ljust(32, b"!"))
    _assert_rejected(lambda: synth.validate_synthetic_runtime_authorization(auth, spec=SPEC, source=SOURCE))


def test_foreign_process_cannot_issue_or_validate_authority(monkeypatch):
    auth = _issue()
    pid = auth.issuer_process_id
    monkeypatch.setattr(synth.os, "getpid", lambda: pid + 1)
    _assert_rejected(lambda: _issue())
    _assert_rejected(lambda: synth.validate_synthetic_runtime_authorization(auth, spec=SPEC, source=SOURCE))


def test_verification_reports_requested_facts_without_runtime_effects():
    with no_runtime_effects(strict=True) as evidence:
        auth, report = synth.verify()
        assert synth.validate_synthetic_runtime_authorization(auth, spec=SPEC, source=SOURCE) is auth
        assert report["phase_id"] == "SYNTH.AUTH.1"
        assert report["status"] == "SYNTH_AUTH_1_COMPLETE"
        assert report["supported_scenario_count"] == 1
        assert report["synthetic_authorizations_issued"] == 1
        assert report["requested_semantic_facts"] == {"before": 10, "return": True, "after": 7}
        assert report["measured_observations"] is None
        assert report["positive_runtime_receipt"] is None
        assert report["execution_ready"] is False
        assert report["execution_completed"] is False
        assert report["reflection_authority"] is False
        assert report["real_runtime_authority_available"] is False
        for field in (
            "compile_count", "jvm_execution_count", "reflection_execution_count",
            "console_count", "bank_execution_count", "real_behavioral_execution_count",
            "synthetic_behavioral_execution_count", "real_runtime_authorizations_consumed",
            "synthetic_runtime_authorizations_consumed", "repository_writes", "apply_actions",
            "model_calls", "author_calls", "phase_containers_created",
        ):
            assert type(report[field]) is int
            assert report[field] == 0
        assert report["source_projected"] is False
        assert report["harness_rendered"] is False
        assert report["spec"]["report_only"] is True
        assert report["synthetic_authorization"]["report_only"] is True
        assert "_signature" not in json.dumps(report)
    assert evidence.denied_attempts == {}
