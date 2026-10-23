"""SYNTH.REFLECT.1 proves exact read-only requests without running Java."""

from __future__ import annotations

import copy
from contextlib import contextmanager
import dataclasses
import hashlib
import json

import pytest

from core.runtime.synthetic import synthetic_read_only_reflection as reflect
from core.runtime.synthetic import synthetic_runtime_authorization as auth_owner
from tests._preflight_runtime1_guard import no_runtime_effects


REQUEST_FIELDS = tuple(field.name for field in dataclasses.fields(reflect.SyntheticReflectionRequest))
AUTH_FIELDS = tuple(field.name for field in dataclasses.fields(auth_owner.SyntheticRuntimeAuthorization))
OBSERVATION_FIELDS = tuple(
    field.name for field in dataclasses.fields(reflect.SyntheticPrivateFieldObservation)
)
ROLE_FACTORIES = (
    ("exact_private_state_before", reflect.executor1r_before_request),
    ("exact_private_state_after", reflect.executor1r_after_request),
)
FALSE_FLAGS = (
    "reflection_execution_authority", "runtime_authority", "real_task_runtime_authority",
    "repository_write_authority", "apply_authority", "field_write_authority",
    "enumeration_authority", "private_method_authority", "execution_ready",
)


class _StringSubclass(str):
    pass


class _BytesSubclass(bytes):
    pass


class _IntSubclass(int):
    pass


@pytest.fixture(autouse=True)
def _deny_all_runtime_effects():
    # All fixture construction and test operations occur under strict denial.
    # The separate fresh-process replay installs denial before owner import.
    with no_runtime_effects(strict=True) as evidence:
        yield evidence
    assert evidence.denied_attempts == {}


def _issue_authorization():
    return auth_owner.issue_synthetic_runtime_authorization(
        auth_owner.executor1r_decrement_3_spec(),
        source=auth_owner.get_executor1r_decrement_3_source(),
    )


def _constructor_arguments(value):
    return {
        field.name: getattr(value, field.name)
        for field in dataclasses.fields(value) if field.init
    }


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
        return value + "_tampered"
    if type(value) is tuple:
        return value + ("unexpected",)
    return object()


def _assert_rejected(operation):
    with pytest.raises(reflect.SyntheticReflectionError) as caught:
        operation()
    assert isinstance(caught.value, ValueError)
    assert type(caught.value.code) is str and caught.value.code
    assert type(caught.value.reason) is str and caught.value.reason


def _assert_invalid_request(request, authorization=None):
    _assert_rejected(lambda: reflect.validate_synthetic_reflection_request(request))
    _assert_rejected(lambda: reflect.render_synthetic_read_only_reflection(request))
    if authorization is not None:
        assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is False


@pytest.mark.parametrize("role,factory", ROLE_FACTORIES)
def test_exact_owned_requests_bind_the_only_target(role, factory):
    request = factory()
    spec = auth_owner.executor1r_decrement_3_spec()
    metadata = spec.observation_contract.requested_field_metadata
    assert reflect.PHASE_ID == "SYNTH.REFLECT.1"
    assert reflect.COMPLETE == "SYNTH_REFLECT_1_COMPLETE"
    assert type(request) is reflect.SyntheticReflectionRequest
    assert reflect.validate_synthetic_reflection_request(request) is request
    assert request.phase_id == reflect.SCENARIO_PHASE_ID == spec.phase_id
    assert request.scenario_id == reflect.SCENARIO_ID == "synthetic.EXECUTOR.1R.decrement_3"
    assert request.source_sha256 == reflect.SOURCE_SHA256 == metadata.source_sha256
    assert request.source_sha256 == "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
    assert request.definition_sha256 == reflect.DEFINITION_SHA256 == metadata.definition_sha256
    assert request.definition_sha256 == "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d"
    assert (request.owner, request.member, request.declared_type) == (
        "SyntheticStateBox", "value", "int"
    )
    assert request.operation == "read_exact_bound_field"
    assert request.observation_role == role
    assert request.source_kind == reflect.SOURCE_KIND == "phase_owned_synthetic_fixture"
    assert type(request.schema_version) is str and request.schema_version
    assert request.reflection_request_valid is True
    for name in FALSE_FLAGS:
        assert getattr(request, name) is False
    assert type(request.fingerprint) is str
    assert len(request.fingerprint) == 64
    assert all(character in "0123456789abcdef" for character in request.fingerprint)


def test_fresh_requests_have_fresh_provenance_and_pinned_role_fingerprints():
    before1, before2 = reflect.executor1r_before_request(), reflect.executor1r_before_request()
    after1, after2 = reflect.executor1r_after_request(), reflect.executor1r_after_request()
    assert len({id(value) for value in (before1, before2, after1, after2)}) == 4
    assert len({value.issuance_id for value in (before1, before2, after1, after2)}) == 4
    for request in (before1, before2, after1, after2):
        assert type(request.issuance_id) is str and len(request.issuance_id) == 64
        assert all(character in "0123456789abcdef" for character in request.issuance_id)
        assert type(request.issuer_process_id) is int
        assert request.issuer_process_id == reflect.os.getpid()
    assert before1.fingerprint == before2.fingerprint
    assert after1.fingerprint == after2.fingerprint
    assert before1.fingerprint != after1.fingerprint


@pytest.mark.parametrize("role,factory", ROLE_FACTORIES)
@pytest.mark.parametrize("field", REQUEST_FIELDS)
def test_every_live_request_field_is_authenticated_and_pinned(role, factory, field):
    request, authorization = factory(), _issue_authorization()
    with _temporarily_set(request, field, _different(getattr(request, field))):
        _assert_invalid_request(request, authorization)
        _assert_rejected(lambda: request.fingerprint)
        _assert_rejected(lambda: request.as_dict())
    assert reflect.validate_synthetic_reflection_request(request) is request


@pytest.mark.parametrize("field", REQUEST_FIELDS)
def test_every_request_field_rejects_equality_alias_types(field):
    request = reflect.executor1r_before_request()
    original = getattr(request, field)
    if type(original) is str:
        changed = _StringSubclass(original)
    elif type(original) is bool:
        changed = int(original)
    elif type(original) is int:
        changed = _IntSubclass(original)
    else:
        pytest.fail("new request field requires exact immutable type coverage: " + field)
    with _temporarily_set(request, field, changed):
        _assert_invalid_request(request, _issue_authorization())


@pytest.mark.parametrize("field,value", (
    ("phase_id", "SYNTH.REFLECT.1"),
    ("phase_id", "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1"),
    ("scenario_id", "synthetic.EXECUTOR.1R.decrement_4"),
    ("source_sha256", "0" * 64),
    ("definition_sha256", "0" * 64),
    ("owner", "BankAccount"),
    ("owner", "java.lang.Runtime"),
    ("owner", 'SyntheticStateBox.class; Runtime.getRuntime().exec("unauthorized")'),
    ("member", "balance"),
    ("member", 'value"); field.setInt(instance, 0); //'),
    ("declared_type", "Integer"),
    ("declared_type", "java.lang.Integer"),
    ("declared_type", "long"),
    ("declared_type", "double"),
    ("declared_type", "boolean"),
    ("observation_role", "direct_public_return"),
    ("observation_role", "arbitrary_private_state"),
    ("operation", "write_exact_bound_field"),
    ("operation", "getDeclaredFields"),
    ("operation", "getFields"),
    ("operation", "private_method_invocation"),
    ("operation", "getDouble"),
    ("operation", "getLong"),
    ("operation", "getBoolean"),
    ("source_kind", "repository_source"),
))
def test_closed_target_and_operation_rejection_matrix(field, value):
    request, authorization = reflect.executor1r_before_request(), _issue_authorization()
    with _temporarily_set(request, field, value):
        _assert_invalid_request(request, authorization)


@pytest.mark.parametrize("clone_kind", (
    "constructor", "replace", "copy", "deepcopy", "dictionary", "json", "reconstructed_json",
))
@pytest.mark.parametrize("role,factory", ROLE_FACTORIES)
def test_equal_objects_and_serialized_requests_cannot_recreate_provenance(clone_kind, role, factory):
    request = factory()
    if clone_kind == "constructor":
        clone = type(request)(**_constructor_arguments(request))
    elif clone_kind == "replace":
        clone = dataclasses.replace(request)
    elif clone_kind == "copy":
        clone = copy.copy(request)
    elif clone_kind == "deepcopy":
        clone = copy.deepcopy(request)
    elif clone_kind == "dictionary":
        clone = dataclasses.asdict(request)
    elif clone_kind == "json":
        clone = json.loads(json.dumps(request.as_dict()))
    else:
        clone = type(request)(**json.loads(json.dumps(_constructor_arguments(request))))
    assert clone is not request
    _assert_invalid_request(clone, _issue_authorization())


def test_request_subclasses_proxies_wrappers_and_duck_types_rejected():
    request = reflect.executor1r_before_request()

    class RequestSubclass(reflect.SyntheticReflectionRequest):
        pass

    class Proxy:
        def __getattr__(self, name):
            return getattr(request, name)

    for foreign in (RequestSubclass(**_constructor_arguments(request)), Proxy(),
            {"request": request}, None, object(), request.as_dict()):
        _assert_invalid_request(foreign, _issue_authorization())


def test_uninitialized_exact_request_and_missing_slots_fail_closed():
    _assert_invalid_request(object.__new__(reflect.SyntheticReflectionRequest), _issue_authorization())
    request, authorization = reflect.executor1r_before_request(), _issue_authorization()
    for field in REQUEST_FIELDS:
        original = getattr(request, field)
        object.__delattr__(request, field)
        try:
            _assert_invalid_request(request, authorization)
        finally:
            object.__setattr__(request, field, original)
    assert reflect.validate_synthetic_reflection_request(request) is request


def test_request_and_factory_interfaces_have_no_generic_target_or_java_reader_inputs():
    request = reflect.executor1r_before_request()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        request.member = "balance"
    assert not hasattr(request, "__dict__")
    for factory in (reflect.executor1r_before_request, reflect.executor1r_after_request):
        for extra in ({"owner": "BankAccount"}, {"member": "balance"},
                {"declared_type": "double"}, {"reader": "getDouble"},
                {"observation_role": "direct_public_return"}, {"source": b"foreign"}):
            with pytest.raises(TypeError):
                factory(**extra)
    for extra in ({"owner": "BankAccount"}, {"member": "balance"},
            {"reader": "getLong"}, {"operation": "setInt"}, {"instance": object()}):
        with pytest.raises(TypeError):
            reflect.render_synthetic_read_only_reflection(request, **extra)
    for extra in ({"argv": ("java", "SyntheticStateBox")},
            {"command": "docker run unauthorized"}, {"shell": True}):
        with pytest.raises(TypeError):
            type(request)(**_constructor_arguments(request), **extra)


@pytest.mark.parametrize("field", ("owner", "member", "declared_type", "observation_role", "operation"))
def test_request_rejects_mutable_containers_in_scalar_contract_fields(field):
    request = reflect.executor1r_before_request()
    with _temporarily_set(request, field, [getattr(request, field)]):
        _assert_invalid_request(request, _issue_authorization())


def test_exported_request_is_report_only_and_has_no_signature_or_secret():
    request = reflect.executor1r_before_request()
    report = request.as_dict()
    assert report["report_only"] is True
    assert report["reflection_request_valid"] is True
    for name in FALSE_FLAGS:
        assert report[name] is False
    assert "_signature" not in report
    assert not any("secret" in name or "proof" in name for name in report)
    serialized = json.dumps(report)
    assert request._signature not in serialized
    assert json.loads(serialized)["report_only"] is True
    _assert_invalid_request(report, _issue_authorization())


def test_owner_authentication_domain_is_independent_of_synth_auth(monkeypatch):
    request, authorization = reflect.executor1r_before_request(), _issue_authorization()
    assert reflect._SECRET is not auth_owner._SECRET
    with _temporarily_set(request, "_signature", authorization._signature):
        _assert_invalid_request(request, authorization)
    monkeypatch.setattr(reflect, "_SECRET", b"foreign-reflection-process-secret".ljust(32, b"!"))
    _assert_invalid_request(request, authorization)
    assert auth_owner.validate_synthetic_runtime_authorization(
        authorization, spec=auth_owner.executor1r_decrement_3_spec(),
        source=auth_owner.get_executor1r_decrement_3_source(),
    ) is authorization


def test_another_process_cannot_issue_or_validate_requests(monkeypatch):
    request = reflect.executor1r_before_request()
    monkeypatch.setattr(reflect.os, "getpid", lambda: request.issuer_process_id + 1)
    _assert_invalid_request(request)
    _assert_rejected(reflect.executor1r_before_request)
    _assert_rejected(reflect.executor1r_after_request)


def test_exact_synthetic_definition_bytes_and_hash_are_bound():
    source = auth_owner.get_executor1r_decrement_3_source()
    assert type(source) is bytes and len(source) == 239
    assert hashlib.sha256(source).hexdigest() == reflect.SOURCE_SHA256
    assert b"private int value = 10;" in source
    reflect.validate_synthetic_definition(source)


@pytest.mark.parametrize("mutation", (
    lambda source: b"",
    lambda source: source + b"\n",
    lambda source: source[:-1],
    lambda source: bytes([source[0] ^ 1]) + source[1:],
    lambda source: source.replace(b"private int value", b"private long value"),
    lambda source: source.replace(b"private int value", b"private Integer value"),
    lambda source: source.replace(b"private int value", b"private double value"),
    lambda source: source.replace(b"private int value", b"public int value"),
    lambda source: source.replace(b"SyntheticStateBox", b"AnotherStateBox"),
    lambda source: source.replace(b"value", b"other"),
    lambda source: source.replace(b"value = 10", b"value = 11"),
    lambda source: source.replace(b"    private int value = 10;", b"    private int value = 10;\n    private int value = 10;"),
    lambda source: source.decode("utf-8"),
    lambda source: bytearray(source),
    lambda source: memoryview(source),
    lambda source: _BytesSubclass(source),
    lambda source: None,
))
def test_definition_rejects_different_declarations_bytes_and_types(mutation):
    source = auth_owner.get_executor1r_decrement_3_source()
    _assert_rejected(lambda: reflect.validate_synthetic_definition(mutation(source)))


def test_live_requests_and_factories_revalidate_source_binding(monkeypatch):
    request, authorization = reflect.executor1r_before_request(), _issue_authorization()
    source = auth_owner.get_executor1r_decrement_3_source()
    monkeypatch.setattr(auth_owner, "get_executor1r_decrement_3_source",
        lambda: source.replace(b"private int value", b"private long value"))
    _assert_invalid_request(request, authorization)
    _assert_rejected(reflect.executor1r_before_request)
    _assert_rejected(reflect.executor1r_after_request)


def test_request_projection_is_checked_even_if_fingerprint_hash_is_equal(monkeypatch):
    request = reflect.executor1r_before_request()
    fingerprint = request.fingerprint
    monkeypatch.setattr(reflect, "_hash", lambda value: fingerprint)
    with _temporarily_set(request, "member", "another_member"):
        _assert_invalid_request(request, _issue_authorization())


def test_definition_exact_bytes_and_declaration_survive_equal_digest(monkeypatch):
    source = auth_owner.get_executor1r_decrement_3_source()

    class PinnedDigest:
        def __init__(self, value):
            self.value = value

        def hexdigest(self):
            return reflect.DEFINITION_SHA256 if len(self.value) == 23 else reflect.SOURCE_SHA256

    monkeypatch.setattr(reflect, "sha256", PinnedDigest)
    _assert_rejected(lambda: reflect.validate_synthetic_definition(source + b"\n"))
    _assert_rejected(lambda: reflect.validate_synthetic_definition(source.replace(b"value", b"other")))
    # Spoofing both the source provider and hash cannot change the declaration.
    wrong = source.replace(b"private int value = 10;", b"private int other = 10;")
    monkeypatch.setattr(auth_owner, "get_executor1r_decrement_3_source", lambda: wrong)
    _assert_rejected(lambda: reflect.validate_synthetic_definition(wrong))


@pytest.mark.parametrize("role,factory", ROLE_FACTORIES)
def test_renderer_is_exact_bounded_primitive_int_read_only_helper(role, factory):
    request = factory()
    java = reflect.render_synthetic_read_only_reflection(request)
    assert type(java) is str
    assert java == reflect.render_synthetic_read_only_reflection(factory())
    method = "observeSyntheticValueBefore" if role == "exact_private_state_before" else "observeSyntheticValueAfter"
    expected = (
        "private static int " + method + "(SyntheticStateBox instance)\n"
        "        throws ReflectiveOperationException {\n"
        "    Class<?> owner = SyntheticStateBox.class;\n"
        '    java.lang.reflect.Field field = owner.getDeclaredField("value");\n'
        "    field.setAccessible(true);\n"
        "    int observed = field.getInt(instance);\n"
        "    return observed;\n"
        "}\n"
    )
    assert java == expected
    assert "Class<?> owner = SyntheticStateBox.class;" in java
    assert 'Field field = owner.getDeclaredField("value");' in java
    assert "field.setAccessible(true);" in java
    assert "int observed = field.getInt(instance);" in java
    assert java.count("getDeclaredField(") == 1
    assert java.count("setAccessible(") == 1
    assert java.count("getInt(") == 1
    for forbidden in (
        "getDeclaredFields", "getFields(", "getDeclaredMethods", "getMethods(",
        "getDeclaredMethod(", "getMethod(", "Class.forName", "loadClass(",
        "getConstructor", "getDeclaredConstructor", "newInstance(", ".invoke(",
        "setInt(", "field.set(", "getDouble(", "getLong(", "getBoolean(",
        "getByte(", "getShort(", "getFloat(", "getChar(", "field.get(",
        "Runtime.getRuntime", "ProcessBuilder", "System.exit", "decrement(",
        "expected_before", "expected_after",
    ):
        assert forbidden not in java


@pytest.mark.parametrize("role,factory", ROLE_FACTORIES)
def test_compatibility_accepts_each_fresh_authentication_without_consuming_it(role, factory):
    request = factory()
    first, second = _issue_authorization(), _issue_authorization()
    assert first is not second
    for authorization in (first, second):
        before = dataclasses.asdict(authorization)
        for _ in range(2):
            assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is True
        assert dataclasses.asdict(authorization) == before
        assert authorization.synthetic_runtime_authorizations_consumed == 0
        assert authorization.reflection_authority is False
        assert authorization.execution_ready is False
    assert request.reflection_execution_authority is False


@pytest.mark.parametrize("field", AUTH_FIELDS)
def test_compatibility_rejects_every_tampered_authorization_field(field):
    request, authorization = reflect.executor1r_before_request(), _issue_authorization()
    with _temporarily_set(authorization, field, _different(getattr(authorization, field))):
        assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is False
    assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is True


@pytest.mark.parametrize("field,value", (
    ("future_exact_reflection_required", 1),
    ("future_exact_reflection_required", False),
    ("reflection_authority", True),
    ("reflection_authority", 0),
    ("execution_ready", True),
    ("runtime_authority", True),
    ("allowed_runtime_operations", ["direct_public_invocation"]),
    ("scenario_id", _StringSubclass("synthetic.EXECUTOR.1R.decrement_3")),
))
def test_compatibility_rejects_authorization_flag_and_type_aliases(field, value):
    request, authorization = reflect.executor1r_before_request(), _issue_authorization()
    with _temporarily_set(authorization, field, value):
        assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is False


def test_compatibility_rejects_changed_owned_requested_field_metadata():
    request, authorization = reflect.executor1r_before_request(), _issue_authorization()
    spec = auth_owner.executor1r_decrement_3_spec()
    metadata = spec.observation_contract.requested_field_metadata
    for field in dataclasses.fields(metadata):
        with _temporarily_set(metadata, field.name, _different(getattr(metadata, field.name))):
            assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is False
    with _temporarily_set(spec.observation_contract, "roles", ("direct_public_return",)):
        assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is False
    with _temporarily_set(spec.observation_contract, "future_exact_reflection_required", False):
        assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is False


@pytest.mark.parametrize("clone_kind", ("constructor", "replace", "copy", "deepcopy", "dictionary", "json"))
def test_compatibility_rejects_copied_or_exported_authorizations(clone_kind):
    request, authorization = reflect.executor1r_before_request(), _issue_authorization()
    if clone_kind == "constructor":
        clone = type(authorization)(**_constructor_arguments(authorization))
    elif clone_kind == "replace":
        clone = dataclasses.replace(authorization)
    elif clone_kind == "copy":
        clone = copy.copy(authorization)
    elif clone_kind == "deepcopy":
        clone = copy.deepcopy(authorization)
    elif clone_kind == "dictionary":
        clone = authorization.as_dict()
    else:
        clone = json.loads(json.dumps(authorization.as_dict()))
    assert clone is not authorization
    assert reflect.synthetic_reflection_satisfies_authorization(request, clone) is False


def test_compatibility_rejects_bank_and_unrelated_authorization_shapes():
    request = reflect.executor1r_before_request()
    # The unrelated BANK shape is deliberately plain data; matching any
    # authorization-looking strings must not bypass SYNTH.AUTH.1 provenance.
    for unrelated in (None, object(), auth_owner.executor1r_decrement_3_spec(),
            {"phase_id": "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1", "owner": "BankAccount",
                "member": "balance", "declared_type": "double"},
            {"scenario_id": request.scenario_id, "source_sha256": request.source_sha256,
                "future_exact_reflection_required": True}):
        assert reflect.synthetic_reflection_satisfies_authorization(request, unrelated) is False


def test_compatibility_rejects_historical_bank_authorization_object():
    from core import runtime_diagnostic_authorization as bank_owner
    from scripts import replay_preflight_runtime1 as bank_replay
    fixture = bank_replay.planning_fixture("preserve_base_compatibility", source=bank_replay.BANK)
    plan = bank_replay.build_plan(fixture)
    bank_authorization = bank_replay.build(fixture, plan)
    assert type(bank_authorization) is bank_owner.RuntimeDiagnosticAuthorization
    assert bank_authorization.phase_id == "PREFLIGHT.RUNTIME.1"
    assert reflect.synthetic_reflection_satisfies_authorization(
        reflect.executor1r_before_request(), bank_authorization
    ) is False


def _observation_arguments(role="exact_private_state_before", measured_value=123):
    return dict(scenario_id=reflect.SCENARIO_ID, role=role, owner="SyntheticStateBox",
        member="value", declared_type="int", measured_value=measured_value,
        source_sha256=reflect.SOURCE_SHA256, definition_sha256=reflect.DEFINITION_SHA256)


@pytest.mark.parametrize("role", ("exact_private_state_before", "exact_private_state_after"))
@pytest.mark.parametrize("measured_value", (-2147483648, -1, 0, 7, 10, 123, 2147483647))
def test_observation_data_accepts_exact_java_int_without_expected_value_comparison(role, measured_value):
    observation = reflect.SyntheticPrivateFieldObservation(**_observation_arguments(role, measured_value))
    assert reflect.validate_synthetic_private_field_observation(observation) is observation
    assert type(observation.measured_value) is int
    assert observation.measured_value == measured_value
    assert not hasattr(observation, "_signature")
    assert not hasattr(observation, "issuance_id")
    assert not hasattr(observation, "runtime_authority")
    assert not hasattr(observation, "positive_runtime_receipt")
    assert not hasattr(observation, "__dict__")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        observation.measured_value = 0
    _assert_invalid_request(observation, _issue_authorization())


@pytest.mark.parametrize("value", (True, False, 10.0, "10", None, _IntSubclass(10),
    -2147483649, 2147483648, [], {"value": 10}))
def test_observation_rejects_coercion_bool_subclasses_and_non_java_int_range(value):
    _assert_rejected(lambda: reflect.SyntheticPrivateFieldObservation(**_observation_arguments(measured_value=value)))


@pytest.mark.parametrize("field", OBSERVATION_FIELDS)
def test_observation_metadata_and_live_result_types_are_validated(field):
    observation = reflect.SyntheticPrivateFieldObservation(**_observation_arguments())
    changed = 7.0 if field == "measured_value" else _different(getattr(observation, field))
    with _temporarily_set(observation, field, changed):
        _assert_rejected(lambda: reflect.validate_synthetic_private_field_observation(observation))
    constructor = _observation_arguments()
    constructor[field] = changed
    _assert_rejected(lambda: reflect.SyntheticPrivateFieldObservation(**constructor))


@pytest.mark.parametrize("field", OBSERVATION_FIELDS)
def test_observation_rejects_equivalent_foreign_types(field):
    observation = reflect.SyntheticPrivateFieldObservation(**_observation_arguments())
    original = getattr(observation, field)
    changed = _IntSubclass(original) if type(original) is int else _StringSubclass(original)
    with _temporarily_set(observation, field, changed):
        _assert_rejected(lambda: reflect.validate_synthetic_private_field_observation(observation))


def test_observation_remains_data_and_json_cannot_be_used_as_typed_measurement():
    observation = reflect.SyntheticPrivateFieldObservation(**_observation_arguments())
    clone = dataclasses.replace(observation)
    assert reflect.validate_synthetic_private_field_observation(clone) is clone
    for foreign in (dataclasses.asdict(observation), json.loads(json.dumps(dataclasses.asdict(observation))),
            None, object()):
        _assert_rejected(lambda: reflect.validate_synthetic_private_field_observation(foreign))
    for role in ("direct_public_return", "private_state", "exact_private_state_before "):
        _assert_rejected(lambda: reflect.SyntheticPrivateFieldObservation(**_observation_arguments(role)))


def test_observation_subclasses_and_wrappers_are_not_the_exact_typed_result():
    class ObservationSubclass(reflect.SyntheticPrivateFieldObservation):
        pass

    _assert_rejected(lambda: ObservationSubclass(**_observation_arguments()))
    observation = reflect.SyntheticPrivateFieldObservation(**_observation_arguments())

    class Proxy:
        def __getattr__(self, name):
            return getattr(observation, name)

    _assert_rejected(lambda: reflect.validate_synthetic_private_field_observation(Proxy()))


def test_uninitialized_exact_observation_and_missing_slots_fail_closed():
    uninitialized = object.__new__(reflect.SyntheticPrivateFieldObservation)
    _assert_rejected(lambda: reflect.validate_synthetic_private_field_observation(uninitialized))
    observation = reflect.SyntheticPrivateFieldObservation(**_observation_arguments())
    for field in OBSERVATION_FIELDS:
        original = getattr(observation, field)
        object.__delattr__(observation, field)
        try:
            _assert_rejected(lambda: reflect.validate_synthetic_private_field_observation(observation))
        finally:
            object.__setattr__(observation, field, original)
    assert reflect.validate_synthetic_private_field_observation(observation) is observation


def test_incomplete_exact_authorizations_never_satisfy_compatibility():
    request = reflect.executor1r_before_request()
    uninitialized = object.__new__(auth_owner.SyntheticRuntimeAuthorization)
    assert reflect.synthetic_reflection_satisfies_authorization(request, uninitialized) is False
    authorization = _issue_authorization()
    for descriptor in dataclasses.fields(authorization):
        original = getattr(authorization, descriptor.name)
        object.__delattr__(authorization, descriptor.name)
        try:
            assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is False
        finally:
            object.__setattr__(authorization, descriptor.name, original)
    assert reflect.synthetic_reflection_satisfies_authorization(request, authorization) is True


def test_verify_returns_requests_and_report_without_measurements_or_effects(_deny_all_runtime_effects):
    requests, report = reflect.verify()
    assert type(requests) is tuple and len(requests) == 2
    assert tuple(request.observation_role for request in requests) == (
        "exact_private_state_before", "exact_private_state_after"
    )
    for request in requests:
        assert reflect.validate_synthetic_reflection_request(request) is request
    assert report["phase_id"] == "SYNTH.REFLECT.1"
    assert report["status"] == "SYNTH_REFLECT_1_COMPLETE"
    assert report["supported_synthetic_reflection_target_count"] == 1
    assert report["scenario_id"] == reflect.SCENARIO_ID
    assert report["source_sha256"] == reflect.SOURCE_SHA256
    assert report["definition_sha256"] == reflect.DEFINITION_SHA256
    assert (report["owner"], report["member"], report["declared_type"]) == (
        "SyntheticStateBox", "value", "int"
    )
    assert report["allowed_operation"] == "read_exact_bound_field"
    assert tuple(report["supported_roles"]) == ("exact_private_state_before", "exact_private_state_after")
    assert report["fresh_synth_auth_1_compatible"] is True
    assert report["copied_exported_authorization_rejected"] is True
    for name in FALSE_FLAGS:
        assert report[name] is False
    assert report["source_projected"] is False
    assert report["measured_observations"] is None
    assert report["positive_runtime_receipt"] is None
    for name in ("compile_count", "jvm_execution_count", "reflection_execution_count",
            "containers_created", "real_runtime_authorizations_consumed",
            "synthetic_runtime_authorizations_consumed", "repository_writes", "authorization_consumed"):
        assert type(report[name]) is int
        assert report[name] == 0
    assert "_signature" not in json.dumps(report)
    assert _deny_all_runtime_effects.denied_attempts == {}
