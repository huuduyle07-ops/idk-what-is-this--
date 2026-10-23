"""PURE admission checks using source-loaded owners and inert public seams.

No upstream capability is issued, no production registry is seeded, and no
renderer or runtime transition is called. The exact inert upstream dataclasses
stand for validator-authenticated originals only inside the isolated fixture.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager, ExitStack
from copy import copy, deepcopy
from dataclasses import asdict, fields, FrozenInstanceError, replace
import gc
from hashlib import sha256
import importlib
import importlib.util
import inspect
from itertools import count
import json
from pathlib import Path
import sys
from threading import Barrier, Thread
from types import SimpleNamespace
from unittest.mock import patch
from weakref import ref

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core.runtime.synthetic import synthetic_read_only_reflection as production_request
    from core.runtime.synthetic import synthetic_runtime_authorization as old_authorization
    from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as old_runtime
    from core.runtime.synthetic import synthetic_reflection_execution_admission as old_admission
    from core.runtime.synthetic import synthetic_reflection_execution_lifecycle as old_reflection
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned as production_auth
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned_lifecycle as production_runtime


ROOT = Path(__file__).resolve().parents[3]
OWNER_PATH = ROOT / "core/runtime/synthetic/synthetic_reflection_execution_admission_pinned.py"
REQUEST_PATH = ROOT / "core/runtime/synthetic/synthetic_read_only_reflection.py"
AUTH_PATH = ROOT / "core/runtime/synthetic/synthetic_runtime_authorization_pinned.py"
RUNTIME_PATH = ROOT / "core/runtime/synthetic/synthetic_runtime_authorization_pinned_lifecycle.py"
CONTRACT = json.loads((ROOT / "docs/roadmap/phases/"
    "SYNTH_REFLECT_PINNED_CONTRACT_1/contract.json").read_text(encoding="utf-8"))
PRIMITIVE = CONTRACT["primitive"]
ROLES = tuple(PRIMITIVE["roles"])
HELPER_HASHES = {
    "BEFORE": "c88aeea914c88ef17a335a184abe6d5b618a9c0c70a7121621ba67edd9919531",
    "AFTER": "4d85951e886bfedabae50c7f64e8e0fa4985e8fa515e4edab9af0a355b10f4ea",
}
FALSE_AUTHORITY = (
    "runtime_authority", "real_task_runtime_authority", "repository_write_authority",
    "apply_authority", "network_authority", "host_mount_authority", "shell_authority",
    "arbitrary_java_authority", "arbitrary_reflection_authority",
    "private_method_authority", "field_write_authority", "enumeration_authority",
    "executor_authority", "BANK_authority", "compilation_authority",
)
_NAMES = count()


@pytest.fixture(autouse=True)
def pure_scope():
    """Deny production capability/effect APIs before fixture construction."""
    maps = (production_request._ISSUED_REQUESTS, old_authorization._ISSUED_HANDLES,
        old_runtime._AUTHORIZATION_LEASES, old_runtime._LEASES,
        old_admission._ISSUED_ADMISSIONS, old_reflection._ADMISSION_LEASES,
        old_reflection._LEASES, production_auth._LIVE,
        production_auth.provider_owner._LIVE)
    map_before = tuple(dict(mapping) for mapping in maps)
    upstream_store = production_runtime._STORE
    historical_paths = (REQUEST_PATH, AUTH_PATH, RUNTIME_PATH,
        ROOT / "core/runtime/synthetic/synthetic_reflection_execution_admission.py",
        ROOT / "core/runtime/synthetic/synthetic_reflection_execution_lifecycle.py")
    historical_bytes = tuple(path.read_bytes() for path in historical_paths)
    with no_runtime_effects(strict=True) as evidence, ExitStack() as denials:
        production_owner = importlib.import_module(
            "core.runtime.synthetic.synthetic_reflection_execution_admission_pinned")
        admission_store = production_owner._STORE
        modules = (production_request, old_authorization, old_runtime,
            old_admission, old_reflection, production_auth, production_runtime,
            production_auth.provider_owner, production_owner)
        for module in modules:
            for name in tuple(vars(module)):
                if callable(getattr(module, name)) and (
                        name.startswith(("issue_", "consume_", "invalidate_", "render_"))
                        or name in ("_issue", "executor1r_before_request",
                            "executor1r_after_request", "synthetic_reflection_satisfies_authorization",
                            "validate_pinned_java_exact_provider")):
                    denials.enter_context(patch.object(module, name,
                        side_effect=evidence.deny(module.__name__ + "." + name)))
        yield evidence
        assert production_owner._STORE is admission_store
    assert evidence.denied_attempts == {}
    assert tuple(dict(mapping) for mapping in maps) == map_before
    assert production_runtime._STORE is upstream_store
    assert tuple(path.read_bytes() for path in historical_paths) == historical_bytes


def _source_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(path.read_text(encoding="utf-8"), "<inert:pinned-admission:" + name + ">",
        "exec"), vars(module))
    return module


@pytest.fixture
def inert(pure_scope):
    prefix = "_test_pinned_reflection_admission_" + str(next(_NAMES))
    names = tuple(prefix + suffix for suffix in ("_request", "_auth", "_runtime", "_owner"))
    request_owner = _source_module(names[0], REQUEST_PATH)
    auth_owner = _source_module(names[1], AUTH_PATH)
    runtime_owner = _source_module(names[2], RUNTIME_PATH)
    owner = _source_module(names[3], OWNER_PATH)
    runtime_owner.authorization_owner = auth_owner
    owner.reflection_owner = request_owner
    owner.authorization_owner = auth_owner
    owner.runtime_owner = runtime_owner
    invocation = PRIMITIVE["invocation"]
    scenario = auth_owner.PinnedSyntheticScenarioIdentity(
        PRIMITIVE["scenario_id"], PRIMITIVE["source_sha256"], PRIMITIVE["source_size_bytes"],
        PRIMITIVE["definition_sha256"], invocation["owner"], invocation["public_method"],
        invocation["method_signature"], tuple(invocation["arguments"]),
        tuple(invocation["argument_types"]), invocation["return_type"],
        PRIMITIVE["field_owner"], PRIMITIVE["field_name"], PRIMITIVE["field_type"],
        10, True, 7)
    provider_values = {item.name: "1" * 64
        for item in fields(auth_owner.PinnedSyntheticProviderIdentity)}
    provider_values.update(phase_id="RUNTIME.JAVA.PINNED.1C",
        schema_version="runtime_java_pinned_1c_v1",
        owner_identity="core.runtime_java_pinned_provider",
        requirement_profile="RUNTIME.JAVA.PINNED.1",
        requirement_schema="runtime_java_pinned_1_v1",
        target_image_identity=auth_owner.REQUIREMENT.image_identity,
        runtime_sandbox_profile="runtime_sandbox_2_v1",
        runtime_sandbox_policy_sha256="5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75",
        controller_identity_evidence_json='{"inert":true}', cleanup_evidence_json='{"inert":true}')
    provider = auth_owner.PinnedSyntheticProviderIdentity(**provider_values)
    auth = auth_owner.PinnedSyntheticRuntimeAuthorization(auth_owner.OWNER_ID,
        "a" * 64, "b" * 64, owner._ISSUER_PID, scenario, provider, "c" * 64)
    calls = []
    requests = []
    state = SimpleNamespace(current="ISSUED", sequence=[])

    def validate_auth(value, **kwargs):
        calls.append(("auth", value))
        if type(value) is not auth_owner.PinnedSyntheticRuntimeAuthorization or value is not auth:
            raise auth_owner.PinnedSyntheticAuthorizationError(
                "pinned_synthetic_authorization_unauthenticated", "inert exact auth original required")
        return value

    auth_owner.validate_pinned_synthetic_runtime_authorization = validate_auth
    runtime = runtime_owner.PinnedSyntheticRuntimeExecutionLease(auth.authorization_id,
        auth.fingerprint, auth.proof_context_id, owner._ISSUER_PID, scenario, provider,
        runtime_owner.ACTIVATION_POLICY_ID, runtime_owner.ACTIVATION_POLICY_DIGEST,
        "d" * 64, "e" * 64, "f" * 64)

    def validate_request(value):
        calls.append(("request", value))
        if (type(value) is not request_owner.SyntheticReflectionRequest
                or not any(value is original for original in requests)):
            raise request_owner.SyntheticReflectionError("synthetic_reflection_unauthenticated",
                "inert exact request original required")
        return value

    def validate_runtime(value, authorization=None):
        calls.append(("runtime", value, authorization))
        if (type(value) is not runtime_owner.PinnedSyntheticRuntimeExecutionLease
                or value is not runtime or authorization is not auth):
            raise runtime_owner.PinnedSyntheticRuntimeExecutionLeaseError("LEASE_UNAUTHENTICATED",
                "inert exact runtime and authorization originals required")
        validate_auth(authorization)
        return value

    def runtime_state(value, authorization=None):
        calls.append(("state", value, authorization))
        validate_runtime(value, authorization)
        return state.sequence.pop(0) if state.sequence else state.current

    def runtime_fingerprint(value):
        validate_runtime(value, auth)
        return value.stable_fingerprint

    def request(role="BEFORE"):
        # Public construction is inert data; only this test's public seam accepts it.
        value = request_owner.SyntheticReflectionRequest(request_owner.SCHEMA_VERSION,
            PRIMITIVE["scenario_phase_id"], PRIMITIVE["scenario_id"], PRIMITIVE["source_sha256"],
            PRIMITIVE["definition_sha256"], PRIMITIVE["field_owner"], PRIMITIVE["field_name"],
            PRIMITIVE["field_type"], PRIMITIVE["operation"], PRIMITIVE["roles"][role],
            PRIMITIVE["source_kind"], format(len(requests) + 1, "064x"), owner._ISSUER_PID)
        requests.append(value)
        return value

    request_owner.validate_synthetic_reflection_request = validate_request
    runtime_owner.validate_pinned_synthetic_runtime_execution_lease = validate_runtime
    runtime_owner.pinned_synthetic_runtime_execution_lease_state = runtime_state
    runtime_owner.PinnedSyntheticRuntimeExecutionLease.fingerprint = property(runtime_fingerprint)
    for module in (request_owner, auth_owner, runtime_owner):
        for name in tuple(vars(module)):
            if callable(getattr(module, name)) and (name.startswith(("issue_", "consume_",
                    "invalidate_", "render_")) or name in ("_issue", "executor1r_before_request",
                    "executor1r_after_request", "synthetic_reflection_satisfies_authorization")):
                setattr(module, name, pure_scope.deny(module.__name__ + "." + name))
    try:
        yield SimpleNamespace(owner=owner, request_owner=request_owner, auth_owner=auth_owner,
            runtime_owner=runtime_owner, auth=auth, runtime=runtime, request=request,
            requests=requests, state=state, calls=calls, validate_auth=validate_auth,
            validate_request=validate_request, validate_runtime=validate_runtime)
    finally:
        for name in names:
            sys.modules.pop(name, None)


def _issue(inert, role="BEFORE", request=None):
    return inert.owner.issue_pinned_synthetic_reflection_execution_admission(
        inert.auth, inert.runtime, request or inert.request(role), role)


def _reject(inert, operation, code):
    with pytest.raises(inert.owner.PinnedSyntheticReflectionExecutionAdmissionError) as caught:
        operation()
    assert isinstance(caught.value, ValueError)
    assert caught.value.code == code
    assert type(caught.value.reason) is str and caught.value.reason
    return caught.value


@contextmanager
def _edit(value, name, changed):
    original = getattr(value, name)
    object.__setattr__(value, name, changed)
    try:
        yield
    finally:
        object.__setattr__(value, name, original)


def _reconstruct(value, cls=None):
    return (cls or type(value))(**{item.name: getattr(value, item.name)
        for item in fields(value) if item.init})


def _clone(value, kind):
    if kind == "copy":
        return copy(value)
    if kind == "deepcopy":
        return deepcopy(value)
    if kind == "replace":
        return replace(value)
    if kind == "constructor":
        return _reconstruct(value)
    if kind == "JSON":
        return json.loads(json.dumps(asdict(value)))
    if kind == "ID":
        return next(getattr(value, name) for name in ("admission_id", "authorization_id",
            "lease_id", "issuance_id") if hasattr(value, name))
    if kind == "fingerprint":
        return value.fingerprint
    if kind == "wrapper":
        return SimpleNamespace(original=value)
    if kind == "subclass":
        return _reconstruct(value, type("ForeignHandle", (type(value),), {}))
    raise AssertionError(kind)


def _reads(inert, admission):
    owner = inert.owner
    return (lambda: owner.validate_pinned_synthetic_reflection_execution_admission(admission),
        lambda: owner.pinned_synthetic_reflection_execution_admission_fingerprint(admission),
        lambda: admission.fingerprint, lambda: admission.as_dict())


def test_owner_type_schema_and_authentication_domain_are_additive(inert):
    owner = inert.owner
    assert owner.OWNER_ID == CONTRACT["admission_owner"]["owner_identity"]
    assert owner.PHASE_ID == "SYNTH.REFLECT.ADMIT.PINNED.1"
    assert owner.SCHEMA_VERSION == "synthetic_reflection_execution_admission_pinned_1_v1"
    assert owner._DOMAIN == b"CATTUS:SYNTH.REFLECT.ADMIT.PINNED.1:exact-reflection-admission:v1"
    assert type(owner._SECRET) is bytes and len(owner._SECRET) == 32
    assert owner._SECRET not in (old_admission._SECRET, production_auth._SECRET,
        production_runtime._SECRET)
    assert owner._LOCK is not production_runtime._LOCK
    assert not issubclass(owner.PinnedSyntheticReflectionExecutionAdmission,
        old_admission.SyntheticReflectionExecutionAdmission)
    assert not hasattr(owner, "PinnedSyntheticReflectionRequest")
    assert not hasattr(owner, "PinnedSyntheticReflectionExecutionLease")
    assert not any(name.startswith(("consume_", "invalidate_")) for name in vars(owner))


@pytest.mark.parametrize("role", ROLES)
def test_exact_reused_request_issues_inert_authenticated_admission(inert, role):
    request = inert.request(role)
    assert type(request) is inert.request_owner.SyntheticReflectionRequest
    admission = _issue(inert, role, request)
    assert type(admission) is inert.owner.PinnedSyntheticReflectionExecutionAdmission
    assert admission.semantic_role == role
    assert admission.exact_request_observation_role == PRIMITIVE["roles"][role]
    assert admission.fingerprint == admission.stable_fingerprint
    assert len(admission.fingerprint) == 64
    assert inert.owner.validate_pinned_synthetic_reflection_execution_admission(
        admission, inert.auth, inert.runtime, request, role) is admission
    assert inert.owner.pinned_synthetic_reflection_request_satisfies_runtime(
        inert.auth, inert.runtime, request, role) is True
    assert inert.owner.pinned_synthetic_reflection_admission_satisfies_executor(
        admission, inert.auth, inert.runtime, request, role) is True
    assert all(call[2] is inert.auth for call in inert.calls
        if call[0] in ("runtime", "state"))
    assert {call[0] for call in inert.calls} >= {"request", "auth", "runtime", "state"}
    with pytest.raises(FrozenInstanceError):
        admission.semantic_role = "AFTER"


def test_before_and_after_have_separate_permanent_slots(inert):
    before, after = _issue(inert), _issue(inert, "AFTER")
    assert before.admission_id != after.admission_id
    assert len(inert.owner._STORE.admissions) == len(inert.owner._STORE.admission_slots) == 2
    for role in ROLES:
        snapshot = inert.owner._STORE
        _reject(inert, lambda: _issue(inert, role), "DUPLICATE_REFLECTION_ADMISSION")
        assert inert.owner._STORE is snapshot


@pytest.mark.parametrize("role", ROLES)
def test_fresh_request_and_collection_never_reopen_permanent_slot(inert, role):
    request = inert.request(role)
    admission = _issue(inert, role, request)
    weak = ref(admission)
    slot_before = dict(inert.owner._STORE.admission_slots)
    del admission
    gc.collect()
    assert weak() is None
    fresh = inert.request(role)
    assert fresh is not request and fresh.issuance_id != request.issuance_id
    _reject(inert, lambda: _issue(inert, role, fresh), "DUPLICATE_REFLECTION_ADMISSION")
    assert inert.owner._STORE.admission_slots == slot_before


@pytest.mark.parametrize("state", ("CONSUMED", "INVALIDATED", "UNRESOLVED", None, True))
@pytest.mark.parametrize("role", ROLES)
def test_non_issued_or_unresolved_runtime_cannot_issue(inert, state, role):
    inert.state.current = state
    before = inert.owner._STORE
    _reject(inert, lambda: _issue(inert, role),
        "PINNED_RUNTIME_STATE_MISMATCH" if state in ("CONSUMED", "INVALIDATED")
        else "PROOF_UNRESOLVED")
    assert inert.owner._STORE is before


@pytest.mark.parametrize("state", ("ISSUED", "CONSUMED", "INVALIDATED"))
def test_compatibility_is_authenticated_truth_without_publication(inert, state):
    request = inert.request()
    inert.state.current = state
    store = inert.owner._STORE
    assert inert.owner.pinned_synthetic_reflection_request_satisfies_runtime(
        inert.auth, inert.runtime, request, "BEFORE") is True
    assert inert.owner._STORE is store


@pytest.mark.parametrize("upstream,category", (("request", "REFLECTION_REQUEST_UNAUTHENTICATED"),
    ("auth", "PINNED_AUTH_UNAUTHENTICATED"),
    ("runtime", "PINNED_RUNTIME_LEASE_UNAUTHENTICATED")))
@pytest.mark.parametrize("kind", ("copy", "deepcopy", "replace", "constructor", "JSON",
    "ID", "fingerprint", "wrapper", "subclass"))
def test_upstream_copies_reports_aliases_and_subclasses_cannot_issue(inert, upstream, category, kind):
    request = inert.request()
    values = {"request": request, "auth": inert.auth, "runtime": inert.runtime}
    values[upstream] = _clone(values[upstream], kind)
    store = inert.owner._STORE
    _reject(inert, lambda: inert.owner.issue_pinned_synthetic_reflection_execution_admission(
        values["auth"], values["runtime"], values["request"], "BEFORE"), category)
    assert inert.owner._STORE is store
    assert inert.owner.pinned_synthetic_reflection_request_satisfies_runtime(
        values["auth"], values["runtime"], values["request"], "BEFORE") is False


@pytest.mark.parametrize("kind", ("copy", "deepcopy", "replace", "constructor", "JSON",
    "ID", "fingerprint", "wrapper", "subclass"))
def test_admission_requires_exact_live_original(inert, kind):
    request = inert.request()
    admission = _issue(inert, request=request)
    foreign = _clone(admission, kind)
    for operation in (lambda: inert.owner.validate_pinned_synthetic_reflection_execution_admission(foreign),
            lambda: inert.owner.pinned_synthetic_reflection_execution_admission_fingerprint(foreign)):
        _reject(inert, operation, "REFLECTION_ADMISSION_UNAUTHENTICATED")
    assert inert.owner.pinned_synthetic_reflection_admission_satisfies_executor(
        foreign, inert.auth, inert.runtime, request, "BEFORE") is False


@pytest.mark.parametrize("upstream", ("request", "auth", "runtime"))
def test_validator_must_return_same_original_object(inert, upstream, monkeypatch):
    request = inert.request()
    modules = {"request": (inert.request_owner, "validate_synthetic_reflection_request", request),
        "auth": (inert.auth_owner, "validate_pinned_synthetic_runtime_authorization", inert.auth),
        "runtime": (inert.runtime_owner, "validate_pinned_synthetic_runtime_execution_lease", inert.runtime)}
    module, name, original = modules[upstream]
    monkeypatch.setattr(module, name, lambda *args, **kwargs: copy(original))
    categories = {"request": "REFLECTION_REQUEST_UNAUTHENTICATED",
        "auth": "PINNED_AUTH_UNAUTHENTICATED", "runtime": "PINNED_RUNTIME_LEASE_UNAUTHENTICATED"}
    before = inert.owner._STORE
    _reject(inert, lambda: _issue(inert, request=request), categories[upstream])
    assert inert.owner._STORE is before


@pytest.mark.parametrize("upstream", ("request", "auth", "runtime"))
def test_all_reads_reauthenticate_original_upstreams(inert, upstream, monkeypatch):
    admission = _issue(inert)
    modules = {"request": (inert.request_owner, "validate_synthetic_reflection_request"),
        "auth": (inert.auth_owner, "validate_pinned_synthetic_runtime_authorization"),
        "runtime": (inert.runtime_owner, "validate_pinned_synthetic_runtime_execution_lease")}
    module, name = modules[upstream]
    def unavailable(*args, **kwargs):
        raise RuntimeError("inert unknown upstream outage")
    monkeypatch.setattr(module, name, unavailable)
    for read in _reads(inert, admission):
        _reject(inert, read, "PROOF_UNRESOLVED")


@pytest.mark.parametrize("upstream", ("authorization", "runtime", "request"))
def test_optional_upstreams_must_be_retained_originals(inert, upstream):
    request = inert.request()
    admission = _issue(inert, request=request)
    kwargs = {"authorization": inert.auth, "runtime": inert.runtime, "request": request}
    kwargs[upstream] = copy(kwargs[upstream])
    _reject(inert, lambda: inert.owner.validate_pinned_synthetic_reflection_execution_admission(
        admission, **kwargs), "REFLECTION_ADMISSION_UNAUTHENTICATED")


@pytest.mark.parametrize("role", ("before", "AFTER", "exact_private_state_before", 1, True, None))
def test_semantic_roles_are_exact_and_no_aliases_are_accepted(inert, role):
    request = inert.request()
    _reject(inert, lambda: inert.owner.issue_pinned_synthetic_reflection_execution_admission(
        inert.auth, inert.runtime, request, role), "REFLECTION_ROLE_MISMATCH")


@pytest.mark.parametrize("field,changed", (("scenario_id", "other"), ("source_sha256", "0" * 64),
    ("definition_sha256", "0" * 64), ("owner", "OtherBox"), ("member", "other"),
    ("declared_type", "long"), ("operation", "write"), ("source_kind", "caller")))
def test_authenticated_request_scope_mismatch_is_not_authentication_error(inert, field, changed):
    request = inert.request()
    with _edit(request, field, changed):
        _reject(inert, lambda: _issue(inert, request=request), "REFLECTION_SCOPE_MISMATCH")


@pytest.mark.parametrize("field,changed", (("arguments", (True,)), ("source_size_bytes", 239.0),
    ("method_signature", "void SyntheticStateBox.decrement(int)"), ("field_type", "long")))
def test_authenticated_scenario_requires_exact_primitive_and_nested_types(inert, field, changed):
    with _edit(inert.auth.scenario, field, changed):
        _reject(inert, lambda: _issue(inert), "REFLECTION_SCOPE_MISMATCH")


@pytest.mark.parametrize("state", ("CONSUMED", "INVALIDATED"))
def test_terminal_runtime_keeps_authenticated_stable_admission_reads(inert, state):
    request = inert.request()
    admission = _issue(inert, request=request)
    fingerprint, report = admission.fingerprint, admission.as_dict()
    inert.state.current = state
    assert inert.owner.validate_pinned_synthetic_reflection_execution_admission(admission) is admission
    assert admission.fingerprint == fingerprint
    assert admission.as_dict() == report
    assert inert.owner.pinned_synthetic_reflection_admission_satisfies_executor(
        admission, inert.auth, inert.runtime, request, "BEFORE") is False


def test_wrong_process_rejects_before_owner_lock(inert, monkeypatch):
    admission = _issue(inert)
    class ForbiddenLock:
        def __enter__(self):
            raise AssertionError("wrong process reached inherited lock")
        def __exit__(self, *args):
            raise AssertionError("wrong process reached inherited lock")
    monkeypatch.setattr(inert.owner, "_LOCK", ForbiddenLock())
    monkeypatch.setattr(inert.owner.os, "getpid", lambda: inert.owner._ISSUER_PID + 1)
    for operation in (*_reads(inert, admission), lambda: _issue(inert, "AFTER")):
        _reject(inert, operation, "REFLECTION_WRONG_PROCESS")


def test_final_runtime_state_change_publishes_nothing(inert):
    inert.state.sequence[:] = ["ISSUED", "CONSUMED"]
    before = inert.owner._STORE
    _reject(inert, lambda: _issue(inert), "PINNED_RUNTIME_STATE_MISMATCH")
    assert inert.owner._STORE is before
    assert not before.admission_slots and not before.admissions
    # The failed publication does not spend a slot.
    assert _issue(inert).semantic_role == "BEFORE"


def test_failed_record_signing_publishes_nothing(inert, monkeypatch):
    before = inert.owner._STORE
    def unavailable(*args, **kwargs):
        raise RuntimeError("inert signing failure")
    monkeypatch.setattr(inert.owner, "_sign", unavailable)
    with pytest.raises((RuntimeError, inert.owner.PinnedSyntheticReflectionExecutionAdmissionError)):
        _issue(inert)
    assert inert.owner._STORE is before
    assert not before.admission_slots and not before.admissions


def test_concurrent_duplicate_role_has_at_most_one_publication(inert):
    requests = [inert.request(), inert.request()]
    barrier = Barrier(2)
    outcomes = []
    def contender(request):
        barrier.wait(timeout=5)
        try:
            outcomes.append(("admission", _issue(inert, request=request)))
        except inert.owner.PinnedSyntheticReflectionExecutionAdmissionError as error:
            outcomes.append(("error", error.code))
    threads = [Thread(target=contender, args=(request,)) for request in requests]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert sum(kind == "admission" for kind, _ in outcomes) == 1
    assert [value for kind, value in outcomes if kind == "error"] == ["DUPLICATE_REFLECTION_ADMISSION"]
    assert len(inert.owner._STORE.admission_slots) == len(inert.owner._STORE.admissions) == 1


@pytest.mark.parametrize("kind,code,category", (
    ("auth", "pinned_synthetic_authorization_unauthenticated", "PINNED_AUTH_UNAUTHENTICATED"),
    ("auth", "pinned_synthetic_authorization_scope_mismatch", "PINNED_AUTH_SCOPE_MISMATCH"),
    ("auth", "pinned_synthetic_provider_graph_mismatch", "PINNED_PROVIDER_PROVENANCE_MISMATCH"),
    ("runtime", "PINNED_PROVIDER_PROVENANCE_MISMATCH", "PINNED_PROVIDER_PROVENANCE_MISMATCH"),
    ("runtime", "PINNED_AUTH_SCOPE_MISMATCH", "PINNED_AUTH_SCOPE_MISMATCH"),
    ("runtime", "LEASE_UNAUTHENTICATED", "PINNED_RUNTIME_LEASE_UNAUTHENTICATED"),
    ("runtime", "LEASE_ALREADY_CONSUMED", "PINNED_RUNTIME_STATE_MISMATCH"),
    ("runtime", "LEASE_INVALIDATED", "PINNED_RUNTIME_STATE_MISMATCH"),
    ("request", "synthetic_reflection_scope_mismatch", "REFLECTION_SCOPE_MISMATCH"),
    ("request", "synthetic_reflection_unauthenticated", "REFLECTION_REQUEST_UNAUTHENTICATED"),
))
def test_known_upstream_error_category_code_and_reason_are_preserved(inert, monkeypatch,
        kind, code, category):
    classes = {"auth": inert.auth_owner.PinnedSyntheticAuthorizationError,
        "runtime": inert.runtime_owner.PinnedSyntheticRuntimeExecutionLeaseError,
        "request": inert.request_owner.SyntheticReflectionError}
    modules = {"auth": (inert.auth_owner, "validate_pinned_synthetic_runtime_authorization"),
        "runtime": (inert.runtime_owner, "validate_pinned_synthetic_runtime_execution_lease"),
        "request": (inert.request_owner, "validate_synthetic_reflection_request")}
    def fail(*args, **kwargs):
        raise classes[kind](code, "inert upstream reason")
    module, name = modules[kind]
    monkeypatch.setattr(module, name, fail)
    error = _reject(inert, lambda: _issue(inert), category)
    assert error.upstream_code == code
    assert error.upstream_reason == "inert upstream reason"


def test_unknown_validator_failure_is_unresolved_and_preserves_reason(inert, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("unknown inert validator failure")
    monkeypatch.setattr(inert.auth_owner, "validate_pinned_synthetic_runtime_authorization", unavailable)
    error = _reject(inert, lambda: _issue(inert), "PROOF_UNRESOLVED")
    assert error.upstream_reason == "unknown inert validator failure"


def test_provider_is_inherited_and_not_a_direct_input(inert):
    owner = inert.owner
    for name in ("issue_pinned_synthetic_reflection_execution_admission",
            "validate_pinned_synthetic_reflection_execution_admission",
            "pinned_synthetic_reflection_request_satisfies_runtime"):
        assert "provider" not in inspect.signature(getattr(owner, name)).parameters
    with pytest.raises(TypeError):
        owner.issue_pinned_synthetic_reflection_execution_admission(inert.auth,
            inert.runtime, inert.request(), "BEFORE", provider=inert.auth.provider)
    assert _issue(inert).semantic_role == "BEFORE"


def test_admission_projection_contains_no_secret_or_private_hmac(inert):
    admission = _issue(inert)
    report = admission.as_dict()
    dumped = json.dumps(report, sort_keys=True, allow_nan=False)
    assert "secret" not in dumped.lower()
    assert "_signature" not in report and "signature" not in report
    record = inert.owner._STORE.admissions[admission.admission_id]
    assert record.signature not in dumped
    assert inert.owner._SECRET.hex() not in dumped
    assert "registry" not in dumped.lower()
    assert report["report_only"] is True
    assert all(type(getattr(admission, item.name)) in (str, int, bool, tuple)
        for item in fields(admission))
    assert admission.arguments == (3,) and type(admission.arguments[0]) is int
    assert admission.argument_types == ("int",) and type(admission.argument_types[0]) is str
    assert report["arguments"] == [3] and report["argument_types"] == ["int"]


def test_all_broad_authorities_and_compilation_are_false(inert):
    admission = _issue(inert)
    for name in FALSE_AUTHORITY:
        assert getattr(admission, name) is False
    assert admission.as_dict()["compilation_authority"] is False


@pytest.mark.parametrize("role", ROLES)
def test_renderer_identity_and_static_helper_evidence_are_bound_without_rendering(inert, role):
    admission = _issue(inert, role)
    assert admission.renderer_identity == CONTRACT["renderer_binding"]["renderer_identity"]
    assert len(admission.renderer_fingerprint) == 64
    assert HELPER_HASHES[role] in admission.as_dict().values()
    assert admission.renderer_fingerprint != HELPER_HASHES[role]
    assert admission.compilation_authority is False
    # AST reconstruction checks the exact frozen helper bytes without invoking it.
    tree = ast.parse(REQUEST_PATH.read_text(encoding="utf-8"))
    render = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name == "render_synthetic_read_only_reflection")
    assert not any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(render))
    helper_name = "_BEFORE_HELPER" if role == "BEFORE" else "_AFTER_HELPER"
    literal = next(node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == helper_name
            for target in node.targets))
    helper = ast.literal_eval(literal)
    assert type(helper) is str
    assert sha256(helper.encode("utf-8")).hexdigest() == HELPER_HASHES[role]
    assert admission.renderer_helper_sha256 == HELPER_HASHES[role]
    expected_renderer = {"renderer_identity": admission.renderer_identity,
        "renderer_phase": "SYNTH.REFLECT.1", "renderer_schema_version": "synthetic_reflection_request_v1",
        "fixed_helper_sha256": HELPER_HASHES[role]}
    canonical = json.dumps(expected_renderer, sort_keys=True, separators=(",", ":"), allow_nan=False)
    frame = inert.owner._DOMAIN + b"\x00renderer-evidence\x00" + canonical.encode("utf-8")
    assert admission.renderer_fingerprint == sha256(frame).hexdigest()


def test_every_admission_scalar_is_authenticated(inert):
    admission = _issue(inert)
    for item in fields(admission):
        value = getattr(admission, item.name)
        changed = (not value if type(value) is bool else value + 1 if type(value) is int
            else value + ("changed",) if type(value) is tuple else value + "_changed")
        with _edit(admission, item.name, changed):
            with pytest.raises(inert.owner.PinnedSyntheticReflectionExecutionAdmissionError):
                inert.owner.validate_pinned_synthetic_reflection_execution_admission(admission)


def test_strict_canonicalization_and_independent_domain_framing(inert):
    owner = inert.owner
    assert owner._canonical({"z": True, "a": [3, "int", None]}) == '{"a":[3,"int",null],"z":true}'
    for foreign in (1.0, float("nan"), (3,), {1: "key"}, SimpleNamespace(value=3)):
        with pytest.raises((TypeError, ValueError)):
            owner._canonical(foreign)
    frame = owner._framed({"value": 3}, "renderer-evidence")
    assert frame == owner._DOMAIN + b'\x00renderer-evidence\x00{"value":3}'
    assert owner._digest({"value": 3}, "renderer-evidence") == sha256(frame).hexdigest()


def test_projection_binds_all_authenticated_originals_and_fixed_primitive(inert):
    request = inert.request()
    admission = _issue(inert, request=request)
    record = inert.owner._STORE.admissions[admission.admission_id]
    assert record.authorization is inert.auth
    assert record.runtime is inert.runtime
    assert record.request is request
    assert record.admission_ref() is admission
    assert admission.authorization_id == inert.auth.authorization_id
    assert admission.authorization_fingerprint == inert.auth.fingerprint
    assert admission.authorization_proof_context_id == inert.auth.proof_context_id
    assert admission.runtime_lease_id == inert.runtime.lease_id
    assert admission.runtime_lease_fingerprint == inert.runtime.fingerprint
    assert admission.request_issuance_id == request.issuance_id
    assert admission.request_issuing_pid == request.issuer_process_id
    assert admission.request_fingerprint == request.fingerprint
    assert admission.runtime_state_at_issuance == "ISSUED"
    for name in ("scenario_phase_id", "scenario_id", "source_kind", "source_sha256",
            "source_size_bytes", "definition_sha256", "field_owner", "field_name",
            "field_type", "operation"):
        assert getattr(admission, name) == PRIMITIVE[name]
    assert admission.method_signature == PRIMITIVE["invocation"]["method_signature"]
    assert admission.arguments == (3,) and admission.argument_types == ("int",)
    assert admission.behavioral_activation_ready is False
    assert admission.behavioral_readiness_reason == "PROOF_UNRESOLVED"
    assert admission.exact_role_read_only_permission is True
    assert admission.admission_can_prepare_lease_only is True
    assert "expected_before" not in admission.as_dict()
    assert "measured_value" not in admission.as_dict()
    unsigned = admission.as_dict()
    unsigned.pop("report_only")
    unsigned.pop("stable_fingerprint")
    assert admission.stable_fingerprint == inert.owner._digest(unsigned, "admission-fingerprint")
    unsigned.pop("evidence_digest")
    assert admission.evidence_digest == inert.owner._digest(unsigned, "admission-evidence")


def test_permanent_slot_key_excludes_request_proof_and_fingerprint_identifiers(inert):
    request = inert.request()
    initial = inert.owner._STORE
    before = _issue(inert, request=request)
    first = inert.owner._STORE
    key, = first.admission_slots
    encoded = repr(key)
    for required in (inert.owner.OWNER_ID, inert.auth.owner_identity, inert.auth.authorization_id,
            inert.runtime.owner_identity, inert.runtime.lease_id, "BEFORE", "read_exact_bound_field"):
        assert required in encoded
    for excluded in (request.issuance_id, request.fingerprint, before.renderer_fingerprint,
            inert.auth.fingerprint, inert.auth.proof_context_id, inert.runtime.fingerprint):
        assert excluded not in encoded
    assert first.admission_slots[key] == before.admission_id
    assert initial is not first and initial.admissions == initial.admission_slots == {}
    _issue(inert, "AFTER")
    assert inert.owner._STORE is not first
    assert len(first.admissions) == len(first.admission_slots) == 1


@pytest.mark.parametrize("missing", ("authorization", "runtime", "request", "role"))
def test_executor_predicate_requires_all_original_inputs(inert, missing):
    request = inert.request()
    admission = _issue(inert, request=request)
    kwargs = {"authorization": inert.auth, "runtime": inert.runtime, "request": request, "role": "BEFORE"}
    kwargs[missing] = None
    assert inert.owner.pinned_synthetic_reflection_admission_satisfies_executor(admission, **kwargs) is False


@pytest.mark.parametrize("role", ("AFTER", "before", "exact_private_state_before", 1, True))
def test_supplied_validation_role_must_equal_retained_semantic_role(inert, role):
    admission = _issue(inert)
    _reject(inert, lambda: inert.owner.validate_pinned_synthetic_reflection_execution_admission(
        admission, role=role), "REFLECTION_ROLE_MISMATCH")


def test_old_admission_type_and_schema_relabel_cannot_authenticate(inert):
    # This is an uninitialized inert data object, never an old issued handle.
    old = object.__new__(old_admission.SyntheticReflectionExecutionAdmission)
    _reject(inert, lambda: inert.owner.validate_pinned_synthetic_reflection_execution_admission(old),
        "REFLECTION_ADMISSION_UNAUTHENTICATED")
    admission = _issue(inert)
    with _edit(admission, "schema_version", old_admission.SCHEMA_VERSION):
        with pytest.raises(inert.owner.PinnedSyntheticReflectionExecutionAdmissionError):
            inert.owner.validate_pinned_synthetic_reflection_execution_admission(admission)


def test_equal_primitive_aliases_do_not_satisfy_scope_or_role(inert):
    class StringAlias(str):
        pass
    class IntegerAlias(int):
        pass
    request = inert.request()
    _reject(inert, lambda: inert.owner.issue_pinned_synthetic_reflection_execution_admission(
        inert.auth, inert.runtime, request, StringAlias("BEFORE")), "REFLECTION_ROLE_MISMATCH")
    with _edit(request, "owner", StringAlias("SyntheticStateBox")):
        _reject(inert, lambda: _issue(inert, request=request), "REFLECTION_SCOPE_MISMATCH")
    with _edit(inert.auth.scenario, "arguments", (IntegerAlias(3),)):
        _reject(inert, lambda: _issue(inert, request=request), "REFLECTION_SCOPE_MISMATCH")


@pytest.mark.parametrize("field", ("authorization_id", "authorization_fingerprint", "authorization_proof_context_id"))
def test_runtime_must_bind_the_same_authenticated_authorization_graph(inert, field):
    with _edit(inert.runtime, field, "0" * 64):
        _reject(inert, lambda: _issue(inert), "PINNED_AUTH_SCOPE_MISMATCH")


def test_runtime_scenario_is_checked_independently_of_authorization(inert):
    distinct = replace(inert.runtime.scenario, method_name="other")
    with _edit(inert.runtime, "scenario", distinct):
        _reject(inert, lambda: _issue(inert), "REFLECTION_SCOPE_MISMATCH")


def test_issuance_has_two_public_authenticated_runtime_state_checks(inert):
    inert.calls.clear()
    _issue(inert)
    states = [call for call in inert.calls if call[0] == "state"]
    assert len(states) == 2
    assert all(call[1] is inert.runtime and call[2] is inert.auth for call in states)


@pytest.mark.parametrize("handle", ("request", "auth", "runtime", "admission"))
@pytest.mark.parametrize("pid_kind", ("wrong_int", "bool", "float", "integer_alias"))
def test_wrong_issuing_pid_on_each_exact_supplied_handle_rejects_before_lock(inert, monkeypatch,
        handle, pid_kind):
    request = inert.request()
    admission = _issue(inert, request=request)
    originals = {"request": request, "auth": inert.auth, "runtime": inert.runtime, "admission": admission}
    class ForbiddenLock:
        def __enter__(self):
            raise AssertionError("foreign exact handle reached owner lock")
        def __exit__(self, *args):
            raise AssertionError("foreign exact handle reached owner lock")
    monkeypatch.setattr(inert.owner, "_LOCK", ForbiddenLock())
    pid_field = "issuer_process_id" if handle == "request" else "issuing_pid"
    operations = [lambda: inert.owner.validate_pinned_synthetic_reflection_execution_admission(
        admission, inert.auth, inert.runtime, request, "BEFORE")]
    if handle == "admission":
        operations.extend(_reads(inert, admission))
    else:
        operations.append(lambda: _issue(inert, request=request))
    class IntegerAlias(int):
        pass
    changed_pid = {"wrong_int": inert.owner._ISSUER_PID + 1, "bool": True,
        "float": float(inert.owner._ISSUER_PID),
        "integer_alias": IntegerAlias(inert.owner._ISSUER_PID)}[pid_kind]
    with _edit(originals[handle], pid_field, changed_pid):
        for operation in operations:
            _reject(inert, operation, "REFLECTION_WRONG_PROCESS")

