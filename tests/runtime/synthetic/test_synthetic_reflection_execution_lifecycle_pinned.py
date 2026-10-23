"""PURE source-loaded lifecycle tests with inert exact-original public seams.

No production effect is called and no production validator is replaced. Test-only
upstream dataclasses are inert data accepted solely by the isolated public
seams. Only the source-loaded new lifecycle issues or transitions test handles.
No renderer, reflection read, method invocation or runtime consumer is called.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import builtins
from copy import copy, deepcopy
from dataclasses import asdict, fields, FrozenInstanceError, replace
import gc
from hashlib import sha256
import importlib
import importlib.util
import inspect
import io
from itertools import count
import json
import os
from pathlib import Path
import sys
import socket
from threading import Barrier, Thread
from types import SimpleNamespace
from unittest.mock import patch
from weakref import ref

import pytest


class _EffectDenialEvidence:
    def __init__(self):
        self.denied_attempts = {}

    def deny(self, effect):
        def forbidden(*args, **kwargs):
            self.denied_attempts[effect] = self.denied_attempts.get(effect, 0) + 1
            raise AssertionError("PURE pinned reflection lifecycle effect denied: " + effect)
        return forbidden


@contextmanager
def no_runtime_effects(*, strict=True):
    """Deny effects using standard-library seams, without application bootstrap.

    This deliberately imports no pipeline, web or config module. Importing the
    historical preflight guard would bootstrap unrelated storage/log writers.
    Filesystem writes are denied during collection imports and every test.
    """
    evidence = _EffectDenialEvidence()
    with ExitStack() as guards:
        guards.enter_context(patch.object(sys, "dont_write_bytecode", True))
        active = [True]
        def audit_denial(event, args):
            if active[0] and (event in {"subprocess.Popen", "os.system", "os.exec",
                    "os.posix_spawn", "os.spawn", "pty.spawn", "os.startfile"}
                    or event.startswith("os.startfile/")):
                evidence.deny("audit:" + event)(*args)
        sys.addaudithook(audit_denial)
        guards.callback(active.__setitem__, 0, False)
        for target in ("subprocess.Popen", "subprocess.run", "subprocess.call",
                "subprocess.check_call", "subprocess.check_output", "os.system", "os.popen",
                "multiprocessing.Process.start", "asyncio.create_subprocess_exec",
                "asyncio.create_subprocess_shell", "socket.create_connection", "socket.socket.connect",
                "socket.socket.connect_ex", "socket.socket.bind", "builtins.input"):
            guards.enter_context(patch(target, side_effect=evidence.deny(target)))
        for name in dir(os):
            if name.startswith(("spawn", "exec")) or name in {
                    "startfile", "fork", "forkpty", "openpty", "posix_spawn", "posix_spawnp"}:
                guards.enter_context(patch.object(os, name, side_effect=evidence.deny("os." + name)))
        if sys.platform == "win32":
            import _winapi
            guards.enter_context(patch.object(_winapi, "CreateProcess",
                side_effect=evidence.deny("_winapi.CreateProcess")))
        for target in ("pathlib.Path.write_bytes", "pathlib.Path.write_text", "os.rename", "os.replace",
                "os.remove", "os.unlink", "os.mkdir", "os.makedirs", "os.rmdir"):
            guards.enter_context(patch(target, side_effect=evidence.deny(target)))
        original_open = builtins.open
        def read_only_open(file, mode="r", *args, **kwargs):
            if any(flag in mode for flag in ("w", "a", "x", "+")):
                return evidence.deny("filesystem_write")(file, mode)
            return original_open(file, mode, *args, **kwargs)
        guards.enter_context(patch("builtins.open", read_only_open))
        guards.enter_context(patch("io.open", read_only_open))
        original_os_open = os.open
        def read_only_os_open(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                return evidence.deny("filesystem_write")(path, flags)
            return original_os_open(path, flags, *args, **kwargs)
        guards.enter_context(patch("os.open", read_only_os_open))
        yield evidence

with no_runtime_effects(strict=False):
    from core.runtime.synthetic import synthetic_read_only_reflection as production_request
    from core.runtime.synthetic import synthetic_runtime_authorization as old_authorization
    from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as old_runtime
    from core.runtime.synthetic import synthetic_reflection_execution_admission as old_admission
    from core.runtime.synthetic import synthetic_reflection_execution_lifecycle as old_reflection
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned as production_auth
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned_lifecycle as production_runtime
    from core.runtime.synthetic import synthetic_reflection_execution_admission_pinned as production_admission


ROOT = Path(__file__).resolve().parents[3]
OWNER_PATH = ROOT / "core/runtime/synthetic/synthetic_reflection_execution_lifecycle_pinned.py"
REQUEST_PATH = ROOT / "core/runtime/synthetic/synthetic_read_only_reflection.py"
AUTH_PATH = ROOT / "core/runtime/synthetic/synthetic_runtime_authorization_pinned.py"
RUNTIME_PATH = ROOT / "core/runtime/synthetic/synthetic_runtime_authorization_pinned_lifecycle.py"
ADMISSION_PATH = ROOT / "core/runtime/synthetic/synthetic_reflection_execution_admission_pinned.py"
CONTRACT = json.loads((ROOT / "docs/roadmap/phases/"
    "SYNTH_REFLECT_PINNED_CONTRACT_1/contract.json").read_text(encoding="utf-8"))
PRIMITIVE = CONTRACT["primitive"]
ROLES = tuple(PRIMITIVE["roles"])
STATES = ("ISSUED", "CONSUMED", "INVALIDATED")
FALSE_AUTHORITY = (
    "runtime_authority", "real_task_runtime_authority", "repository_write_authority",
    "apply_authority", "network_authority", "host_mount_authority", "shell_authority",
    "arbitrary_java_authority", "arbitrary_reflection_authority", "arbitrary_class_authority",
    "arbitrary_method_authority", "private_method_authority", "field_write_authority",
    "enumeration_authority", "executor_authority", "BANK_authority", "compilation_authority",
    "constructor_reflection_authority", "arbitrary_class_loading_authority",
)
API_NAMES = (
    "issue_pinned_synthetic_reflection_execution_lease",
    "validate_pinned_synthetic_reflection_execution_lease",
    "pinned_synthetic_reflection_execution_lease_fingerprint",
    "pinned_synthetic_reflection_execution_lease_state",
    "check_pinned_synthetic_reflection_execution_lease_preexecution_readiness",
    "check_pinned_synthetic_reflection_execution_lease_active_readiness",
    "consume_pinned_synthetic_reflection_execution_lease",
    "invalidate_pinned_synthetic_reflection_execution_lease",
)
_NAMES = count()


@pytest.fixture(autouse=True)
def pure_scope():
    """Snapshot production owners and deny effects without patching validators."""
    maps = (production_request._ISSUED_REQUESTS, old_authorization._ISSUED_HANDLES,
        old_runtime._AUTHORIZATION_LEASES, old_runtime._LEASES,
        old_admission._ISSUED_ADMISSIONS, old_reflection._ADMISSION_LEASES,
        old_reflection._LEASES, production_auth._LIVE,
        production_auth.provider_owner._LIVE)
    map_before = tuple(dict(mapping) for mapping in maps)
    stores = (production_runtime._STORE, production_admission._STORE)
    modules = (production_request, old_authorization, old_runtime,
        old_admission, old_reflection, production_auth, production_runtime,
        production_auth.provider_owner, production_admission)
    validators = {(module, name): value for module in modules
        for name, value in vars(module).items()
        if name.startswith("validate_") and callable(value)}
    history = (REQUEST_PATH, AUTH_PATH, RUNTIME_PATH, ADMISSION_PATH,
        ROOT / "core/runtime/synthetic/synthetic_reflection_execution_admission.py",
        ROOT / "core/runtime/synthetic/synthetic_reflection_execution_lifecycle.py")
    historical_bytes = tuple(path.read_bytes() for path in history)
    with no_runtime_effects(strict=True) as evidence, ExitStack() as denials:
        production_owner = importlib.import_module(
            "core.runtime.synthetic.synthetic_reflection_execution_lifecycle_pinned")
        owner_store = production_owner._STORE
        for module in (*modules, production_owner):
            for name, value in tuple(vars(module).items()):
                if callable(value) and (name.startswith(("issue_", "consume_", "invalidate_", "render_"))
                        or name in ("_issue", "executor1r_before_request", "executor1r_after_request",
                            "synthetic_reflection_satisfies_authorization")):
                    denials.enter_context(patch.object(module, name,
                        side_effect=evidence.deny(module.__name__ + "." + name)))
        yield evidence
        assert production_owner._STORE is owner_store
    assert evidence.denied_attempts == {}
    assert tuple(dict(mapping) for mapping in maps) == map_before
    assert production_runtime._STORE is stores[0]
    assert production_admission._STORE is stores[1]
    assert all(getattr(module, name) is value for (module, name), value in validators.items())
    assert tuple(path.read_bytes() for path in history) == historical_bytes


def _source_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(path.read_text(encoding="utf-8"),
        "<isolated:pinned-reflection-lifecycle:" + name + ">", "exec"), vars(module))
    return module


def _framed_digest(domain, role, payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(domain + b"\x00" + role.encode("utf-8") + b"\x00"
        + canonical.encode("utf-8")).hexdigest()


@pytest.fixture
def inert(pure_scope):
    prefix = "_test_pinned_reflection_lifecycle_" + str(next(_NAMES))
    names = tuple(prefix + suffix for suffix in ("_request", "_auth", "_runtime", "_admission", "_owner"))
    request_owner = _source_module(names[0], REQUEST_PATH)
    auth_owner = _source_module(names[1], AUTH_PATH)
    runtime_owner = _source_module(names[2], RUNTIME_PATH)
    admission_owner = _source_module(names[3], ADMISSION_PATH)
    owner = _source_module(names[4], OWNER_PATH)
    runtime_owner.authorization_owner = auth_owner
    admission_owner.reflection_owner = request_owner
    admission_owner.authorization_owner = auth_owner
    admission_owner.runtime_owner = runtime_owner
    owner.reflection_owner = request_owner
    owner.authorization_owner = auth_owner
    owner.runtime_owner = runtime_owner
    owner.admission_owner = admission_owner
    invocation = PRIMITIVE["invocation"]
    scenario = auth_owner.PinnedSyntheticScenarioIdentity(
        PRIMITIVE["scenario_id"], PRIMITIVE["source_sha256"], PRIMITIVE["source_size_bytes"],
        PRIMITIVE["definition_sha256"], invocation["owner"], invocation["public_method"],
        invocation["method_signature"], tuple(invocation["arguments"]),
        tuple(invocation["argument_types"]), invocation["return_type"],
        PRIMITIVE["field_owner"], PRIMITIVE["field_name"], PRIMITIVE["field_type"], 10, True, 7)
    provider_values = {item.name: "1" * 64
        for item in fields(auth_owner.PinnedSyntheticProviderIdentity)}
    provider_values.update(phase_id="RUNTIME.JAVA.PINNED.1C",
        schema_version="runtime_java_pinned_1c_v1",
        owner_identity="core.runtime_java_pinned_provider",
        requirement_profile="RUNTIME.JAVA.PINNED.1", requirement_schema="runtime_java_pinned_1_v1",
        target_image_identity=auth_owner.REQUIREMENT.image_identity,
        runtime_sandbox_profile="runtime_sandbox_2_v1",
        runtime_sandbox_policy_sha256="5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75",
        controller_identity_evidence_json='{"inert":true}', cleanup_evidence_json='{"inert":true}')
    provider = auth_owner.PinnedSyntheticProviderIdentity(**provider_values)
    authorization = auth_owner.PinnedSyntheticRuntimeAuthorization(auth_owner.OWNER_ID,
        "a" * 64, "b" * 64, owner._ISSUER_PID, scenario, provider, "c" * 64)
    calls, requests, admissions = [], [], []
    state = SimpleNamespace(current="ISSUED", sequence=[])

    def validate_auth(value, **kwargs):
        calls.append(("auth", value))
        if type(value) is not auth_owner.PinnedSyntheticRuntimeAuthorization or value is not authorization:
            raise auth_owner.PinnedSyntheticAuthorizationError(
                "pinned_synthetic_authorization_unauthenticated", "inert exact auth original required")
        return value

    auth_owner.validate_pinned_synthetic_runtime_authorization = validate_auth
    runtime = runtime_owner.PinnedSyntheticRuntimeExecutionLease(authorization.authorization_id,
        authorization.fingerprint, authorization.proof_context_id, owner._ISSUER_PID, scenario, provider,
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
                or value is not runtime or authorization is not inert_authorization):
            raise runtime_owner.PinnedSyntheticRuntimeExecutionLeaseError("LEASE_UNAUTHENTICATED",
                "inert exact runtime/auth originals required")
        validate_auth(authorization)
        return value

    inert_authorization = authorization

    def runtime_state(value, authorization=None):
        calls.append(("state", value, authorization))
        validate_runtime(value, authorization)
        return state.sequence.pop(0) if state.sequence else state.current

    def runtime_fingerprint(value):
        validate_runtime(value, authorization)
        return value.stable_fingerprint

    def validate_admission(value, authorization=None, runtime=None, request=None, role=None):
        calls.append(("admission", value, authorization, runtime, request, role))
        binding = next((original for original in admissions if original.admission is value), None)
        if type(value) is not admission_owner.PinnedSyntheticReflectionExecutionAdmission or binding is None:
            raise admission_owner.PinnedSyntheticReflectionExecutionAdmissionError(
                "REFLECTION_ADMISSION_UNAUTHENTICATED", "inert exact admission original required")
        if any(supplied is not None and supplied is not retained for supplied, retained in (
                (authorization, inert_authorization), (runtime, inert_runtime), (request, binding.request))):
            raise admission_owner.PinnedSyntheticReflectionExecutionAdmissionError(
                "REFLECTION_ADMISSION_UNAUTHENTICATED", "inert retained originals required")
        if role is not None and (type(role) is not str or role != binding.role):
            raise admission_owner.PinnedSyntheticReflectionExecutionAdmissionError(
                "REFLECTION_ROLE_MISMATCH", "inert exact role required")
        return value

    inert_runtime = runtime

    def admission_fingerprint(value):
        validate_admission(value)
        return value.stable_fingerprint

    def request(role="BEFORE"):
        value = request_owner.SyntheticReflectionRequest(request_owner.SCHEMA_VERSION,
            PRIMITIVE["scenario_phase_id"], PRIMITIVE["scenario_id"], PRIMITIVE["source_sha256"],
            PRIMITIVE["definition_sha256"], PRIMITIVE["field_owner"], PRIMITIVE["field_name"],
            PRIMITIVE["field_type"], PRIMITIVE["operation"], PRIMITIVE["roles"][role],
            PRIMITIVE["source_kind"], format(len(requests) + 1, "064x"), owner._ISSUER_PID)
        requests.append(value)
        return value

    def admission(role="BEFORE", bound_request=None):
        bound_request = bound_request or request(role)
        helper = admission_owner.BEFORE_HELPER_SHA256 if role == "BEFORE" else admission_owner.AFTER_HELPER_SHA256
        renderer = {"renderer_identity": admission_owner.RENDERER_IDENTITY,
            "renderer_phase": admission_owner.RENDERER_PHASE,
            "renderer_schema_version": admission_owner.RENDERER_SCHEMA, "fixed_helper_sha256": helper}
        value = admission_owner.PinnedSyntheticReflectionExecutionAdmission(
            format(len(admissions) + 100, "064x"), owner._ISSUER_PID, role, PRIMITIVE["roles"][role],
            authorization.owner_identity, authorization.phase_id, authorization.schema_version,
            authorization.issuing_pid, authorization.authorization_id, authorization.fingerprint,
            authorization.proof_context_id, runtime.owner_identity, runtime.phase_id, runtime.schema_version,
            runtime.issuing_pid, runtime.lease_id, runtime.fingerprint, bound_request.issuance_id,
            bound_request.issuer_process_id, bound_request.fingerprint, helper,
            _framed_digest(admission_owner._DOMAIN, "renderer-evidence", renderer), "2" * 64,
            sha256(("inert admission " + str(len(admissions))).encode("utf-8")).hexdigest())
        admissions.append(SimpleNamespace(admission=value, request=bound_request, role=role))
        return value

    request_owner.validate_synthetic_reflection_request = validate_request
    runtime_owner.validate_pinned_synthetic_runtime_execution_lease = validate_runtime
    runtime_owner.pinned_synthetic_runtime_execution_lease_state = runtime_state
    runtime_owner.PinnedSyntheticRuntimeExecutionLease.fingerprint = property(runtime_fingerprint)
    admission_owner.validate_pinned_synthetic_reflection_execution_admission = validate_admission
    admission_owner.PinnedSyntheticReflectionExecutionAdmission.fingerprint = property(admission_fingerprint)
    for module in (request_owner, auth_owner, runtime_owner, admission_owner):
        for name, value in tuple(vars(module).items()):
            if callable(value) and (name.startswith(("issue_", "consume_", "invalidate_", "render_"))
                    or name in ("_issue", "executor1r_before_request", "executor1r_after_request",
                        "synthetic_reflection_satisfies_authorization")):
                setattr(module, name, pure_scope.deny(module.__name__ + "." + name))
    try:
        yield SimpleNamespace(owner=owner, request_owner=request_owner, auth_owner=auth_owner,
            runtime_owner=runtime_owner, admission_owner=admission_owner, auth=authorization,
            runtime=runtime, request=request, admission=admission, requests=requests, admissions=admissions,
            calls=calls, state=state, validate_auth=validate_auth, validate_request=validate_request,
            validate_runtime=validate_runtime, validate_admission=validate_admission,
            runtime_state=runtime_state)
    finally:
        for name in names:
            sys.modules.pop(name, None)


def _binding(inert, admission):
    return next(binding for binding in inert.admissions if binding.admission is admission)


def _issue(inert, role="BEFORE", admission=None):
    admission = admission or inert.admission(role)
    binding = _binding(inert, admission)
    return inert.owner.issue_pinned_synthetic_reflection_execution_lease(
        admission, inert.auth, inert.runtime, binding.request, role)


def _reject(inert, operation, code):
    with pytest.raises(inert.owner.PinnedSyntheticReflectionExecutionLeaseError) as caught:
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


def _reads(inert, lease):
    owner = inert.owner
    return (lambda: owner.validate_pinned_synthetic_reflection_execution_lease(lease),
        lambda: owner.pinned_synthetic_reflection_execution_lease_state(lease),
        lambda: owner.pinned_synthetic_reflection_execution_lease_fingerprint(lease),
        lambda: lease.fingerprint, lambda: lease.as_dict(),
        lambda: owner.check_pinned_synthetic_reflection_execution_lease_preexecution_readiness(lease),
        lambda: owner.check_pinned_synthetic_reflection_execution_lease_active_readiness(lease))


def _operations(inert, lease):
    return (*_reads(inert, lease),
        lambda: inert.owner.consume_pinned_synthetic_reflection_execution_lease(lease),
        lambda: inert.owner.invalidate_pinned_synthetic_reflection_execution_lease(lease))


def test_distinct_owner_type_schema_domain_and_public_apis(inert):
    owner = inert.owner
    assert owner.OWNER_ID == "core.synthetic_reflection_execution_lifecycle_pinned"
    assert owner.PHASE_ID == "SYNTH.REFLECT.LIFECYCLE.PINNED.1"
    assert owner.SCHEMA_VERSION == "synthetic_reflection_execution_lease_pinned_1_v1"
    assert owner._DOMAIN == b"CATTUS:SYNTH.REFLECT.LIFECYCLE.PINNED.1:exact-reflection-lease:v1"
    assert type(owner._SECRET) is bytes and len(owner._SECRET) == 32
    assert owner._SECRET not in (old_reflection._SECRET, production_admission._SECRET,
        production_runtime._SECRET, production_auth._SECRET)
    assert owner._LOCK is not old_reflection._LOCK
    assert owner._LOCK is not production_admission._LOCK
    assert owner._LOCK is not production_runtime._LOCK
    assert not issubclass(owner.PinnedSyntheticReflectionExecutionLease,
        old_reflection.SyntheticReflectionExecutionLease)
    assert all(callable(getattr(owner, name)) for name in API_NAMES)
    assert {owner.ISSUED, owner.CONSUMED, owner.INVALIDATED} == set(STATES)


@pytest.mark.parametrize("role", ROLES)
def test_inert_issue_binds_all_originals_and_immutable_projection(inert, role):
    admission = inert.admission(role)
    request = _binding(inert, admission).request
    lease = _issue(inert, role, admission)
    owner = inert.owner
    assert type(lease) is owner.PinnedSyntheticReflectionExecutionLease
    assert owner.validate_pinned_synthetic_reflection_execution_lease(
        lease, admission, inert.auth, inert.runtime, request, role) is lease
    record = owner._STORE.leases[lease.lease_id]
    assert record.admission is admission
    assert record.authorization is inert.auth
    assert record.runtime is inert.runtime
    assert record.request is request
    assert record.lease_ref() is lease
    assert lease.admission_id == admission.admission_id
    assert lease.admission_fingerprint == admission.fingerprint
    assert lease.request_issuance_id == request.issuance_id
    assert lease.request_fingerprint == request.fingerprint
    assert lease.authorization_id == inert.auth.authorization_id
    assert lease.authorization_fingerprint == inert.auth.fingerprint
    assert lease.authorization_proof_context_id == inert.auth.proof_context_id
    assert lease.runtime_lease_id == inert.runtime.lease_id
    assert lease.runtime_lease_fingerprint == inert.runtime.fingerprint
    assert lease.semantic_role == role
    assert lease.exact_request_observation_role == PRIMITIVE["roles"][role]
    assert lease.runtime_state_at_issuance == lease.initial_state == "ISSUED"
    for name in ("scenario_phase_id", "scenario_id", "source_kind", "source_sha256",
            "source_size_bytes", "definition_sha256", "field_owner", "field_name", "field_type", "operation"):
        assert getattr(lease, name) == PRIMITIVE[name]
    assert lease.method_signature == PRIMITIVE["invocation"]["method_signature"]
    assert lease.arguments == (3,) and type(lease.arguments[0]) is int
    assert lease.argument_types == ("int",)
    for name in ("renderer_identity", "renderer_helper_sha256", "renderer_fingerprint"):
        assert getattr(lease, name) == getattr(admission, name)
    assert lease.fingerprint == lease.stable_fingerprint
    with pytest.raises(FrozenInstanceError):
        lease.semantic_role = "AFTER"


@pytest.mark.parametrize("upstream,category", (
    ("admission", "REFLECTION_ADMISSION_UNAUTHENTICATED"),
    ("authorization", "PINNED_AUTH_UNAUTHENTICATED"),
    ("runtime", "PINNED_RUNTIME_LEASE_UNAUTHENTICATED"),
    ("request", "REFLECTION_REQUEST_UNAUTHENTICATED")))
@pytest.mark.parametrize("kind", ("copy", "deepcopy", "replace", "constructor", "JSON",
    "ID", "fingerprint", "wrapper", "subclass"))
def test_upstream_copies_reports_ids_and_subclasses_cannot_issue(inert, upstream, category, kind):
    admission = inert.admission()
    values = {"admission": admission, "authorization": inert.auth, "runtime": inert.runtime,
        "request": _binding(inert, admission).request}
    values[upstream] = _clone(values[upstream], kind)
    store = inert.owner._STORE
    _reject(inert, lambda: inert.owner.issue_pinned_synthetic_reflection_execution_lease(
        **values, role="BEFORE"), category)
    assert inert.owner._STORE is store


@pytest.mark.parametrize("kind", ("copy", "deepcopy", "replace", "constructor", "JSON",
    "ID", "fingerprint", "wrapper", "subclass"))
def test_lease_copy_reconstruction_reports_and_ids_never_authenticate(inert, kind):
    lease = _issue(inert)
    foreign = _clone(lease, kind)
    store = inert.owner._STORE
    for operation in _operations(inert, foreign)[:3] + _operations(inert, foreign)[5:]:
        _reject(inert, operation, "REFLECTION_LEASE_UNAUTHENTICATED")
    assert inert.owner._STORE is store


@pytest.mark.parametrize("upstream", ("admission", "auth", "runtime", "request"))
def test_each_public_upstream_validator_is_mandatory_and_requires_same_return(inert, upstream, monkeypatch):
    admission = inert.admission()
    request = _binding(inert, admission).request
    modules = {"admission": (inert.admission_owner,
        "validate_pinned_synthetic_reflection_execution_admission", admission, "REFLECTION_ADMISSION_UNAUTHENTICATED"),
        "auth": (inert.auth_owner, "validate_pinned_synthetic_runtime_authorization", inert.auth,
            "PINNED_AUTH_UNAUTHENTICATED"),
        "runtime": (inert.runtime_owner, "validate_pinned_synthetic_runtime_execution_lease", inert.runtime,
            "PINNED_RUNTIME_LEASE_UNAUTHENTICATED"),
        "request": (inert.request_owner, "validate_synthetic_reflection_request", request,
            "REFLECTION_REQUEST_UNAUTHENTICATED")}
    module, name, original, category = modules[upstream]
    monkeypatch.setattr(module, name, lambda *args, **kwargs: copy(original))
    store = inert.owner._STORE
    _reject(inert, lambda: _issue(inert, admission=admission), category)
    assert inert.owner._STORE is store


@pytest.mark.parametrize("upstream", ("admission", "auth", "runtime", "request", "state"))
def test_all_lifecycle_snapshots_reauthenticate_public_graph(inert, upstream, monkeypatch):
    lease = _issue(inert)
    modules = {"admission": (inert.admission_owner, "validate_pinned_synthetic_reflection_execution_admission"),
        "auth": (inert.auth_owner, "validate_pinned_synthetic_runtime_authorization"),
        "runtime": (inert.runtime_owner, "validate_pinned_synthetic_runtime_execution_lease"),
        "request": (inert.request_owner, "validate_synthetic_reflection_request"),
        "state": (inert.runtime_owner, "pinned_synthetic_runtime_execution_lease_state")}
    def unavailable(*args, **kwargs):
        raise RuntimeError("unknown inert public " + upstream + " validator failure")
    module, name = modules[upstream]
    monkeypatch.setattr(module, name, unavailable)
    store = inert.owner._STORE
    for operation in _operations(inert, lease):
        error = _reject(inert, operation, "PROOF_UNRESOLVED")
        assert error.upstream_reason == "unknown inert public " + upstream + " validator failure"
    assert inert.owner._STORE is store


@pytest.mark.parametrize("upstream", ("admission", "authorization", "runtime", "request"))
def test_optional_upstreams_require_retained_identity(inert, upstream):
    admission = inert.admission()
    lease = _issue(inert, admission=admission)
    kwargs = {"admission": admission, "authorization": inert.auth, "runtime": inert.runtime,
        "request": _binding(inert, admission).request, "role": "BEFORE"}
    kwargs[upstream] = copy(kwargs[upstream])
    for name in API_NAMES[1:]:
        _reject(inert, lambda name=name: getattr(inert.owner, name)(lease, **kwargs),
            "REFLECTION_LEASE_UNAUTHENTICATED")


def test_distinct_same_role_request_cannot_replace_retained_graph(inert):
    admission = inert.admission()
    fresh = inert.request()
    store = inert.owner._STORE
    _reject(inert, lambda: inert.owner.issue_pinned_synthetic_reflection_execution_lease(
        admission, inert.auth, inert.runtime, fresh, "BEFORE"), "REFLECTION_ADMISSION_UNAUTHENTICATED")
    assert inert.owner._STORE is store


@pytest.mark.parametrize("state", ("CONSUMED", "INVALIDATED", "UNRESOLVED", None, True))
@pytest.mark.parametrize("role", ROLES)
def test_issue_requires_current_public_runtime_issued(inert, state, role):
    admission = inert.admission(role)
    inert.state.current = state
    store = inert.owner._STORE
    _reject(inert, lambda: _issue(inert, role, admission),
        "PINNED_RUNTIME_STATE_MISMATCH" if state in ("CONSUMED", "INVALIDATED") else "PROOF_UNRESOLVED")
    assert inert.owner._STORE is store


def test_current_state_is_public_not_immutable_issuance_projection(inert):
    admission = inert.admission()
    lease = _issue(inert, admission=admission)
    assert inert.runtime.initial_state == admission.runtime_state_at_issuance == "ISSUED"
    inert.state.current = "CONSUMED"
    inert.calls.clear()
    report = inert.owner.check_pinned_synthetic_reflection_execution_lease_active_readiness(lease)
    assert report.reflection_active_ready is True
    assert report.runtime_current_state == "CONSUMED"
    assert all(call[1] is inert.runtime and call[2] is inert.auth
        for call in inert.calls if call[0] in ("runtime", "state"))
    assert any(call[0] == "state" for call in inert.calls)


def test_each_read_uses_one_authenticated_runtime_snapshot_under_one_owner_lock(inert, monkeypatch):
    lease = _issue(inert)
    original_lock = inert.owner._LOCK
    entered = []
    class SnapshotLock:
        def __enter__(self):
            original_lock.acquire()
            entered.append("enter")
        def __exit__(self, *args):
            entered.append("exit")
            original_lock.release()
    monkeypatch.setattr(inert.owner, "_LOCK", SnapshotLock())
    for read in _reads(inert, lease):
        inert.calls.clear()
        entered.clear()
        read()
        assert entered == ["enter", "exit"]
        assert len([call for call in inert.calls if call[0] == "state"]) == 1


def test_one_permanent_slot_per_exact_admission_and_roles_are_independent(inert):
    before, after = inert.admission(), inert.admission("AFTER")
    leases = (_issue(inert, admission=before), _issue(inert, "AFTER", after))
    assert leases[0].lease_id != leases[1].lease_id
    assert len(inert.owner._STORE.admission_leases) == len(inert.owner._STORE.leases) == 2
    for role, admission in (("BEFORE", before), ("AFTER", after)):
        store = inert.owner._STORE
        _reject(inert, lambda: _issue(inert, role, admission), "DUPLICATE_REFLECTION_LEASE")
        assert inert.owner._STORE is store


def test_collection_does_not_reopen_permanent_authenticated_admission_slot(inert):
    admission = inert.admission()
    lease = _issue(inert, admission=admission)
    weak = ref(lease)
    slots = dict(inert.owner._STORE.admission_leases)
    del lease
    gc.collect()
    assert weak() is None
    _reject(inert, lambda: _issue(inert, admission=admission), "DUPLICATE_REFLECTION_LEASE")
    assert inert.owner._STORE.admission_leases == slots


def test_permanent_key_is_rooted_in_owner_process_admission_only(inert):
    admission = inert.admission()
    lease = _issue(inert, admission=admission)
    key, = inert.owner._STORE.admission_leases
    encoded = repr(key)
    for required in (admission.owner_identity, admission.phase_id, admission.schema_version,
            str(inert.owner._ISSUER_PID), admission.admission_id):
        assert required in encoded
    for excluded in (inert.auth.authorization_id, inert.auth.proof_context_id,
            inert.auth.fingerprint, inert.runtime.lease_id, inert.runtime.fingerprint,
            lease.request_issuance_id, lease.request_fingerprint, admission.fingerprint,
            "BEFORE", "read_exact_bound_field"):
        assert excluded not in encoded
    assert inert.owner._STORE.admission_leases[key] == lease.lease_id


@pytest.mark.parametrize("terminal", ("CONSUMED", "INVALIDATED"))
def test_stable_fingerprint_and_terminal_validation_survive_state_change(inert, terminal):
    admission = inert.admission()
    lease = _issue(inert, admission=admission)
    fingerprint = lease.fingerprint
    immutable = {item.name: getattr(lease, item.name) for item in fields(lease)}
    original_store = inert.owner._STORE
    initial_record = original_store.leases[lease.lease_id]
    if terminal == "CONSUMED":
        inert.state.current = "CONSUMED"
        inert.owner.consume_pinned_synthetic_reflection_execution_lease(lease)
    else:
        inert.owner.invalidate_pinned_synthetic_reflection_execution_lease(lease)
    current_record = inert.owner._STORE.leases[lease.lease_id]
    assert current_record is not initial_record
    assert current_record.signature != initial_record.signature
    assert current_record.projection_json == initial_record.projection_json
    assert current_record.lifecycle_state == terminal
    assert initial_record.lifecycle_state == "ISSUED"
    assert {item.name: getattr(lease, item.name) for item in fields(lease)} == immutable
    assert lease.fingerprint == fingerprint
    for runtime_state in STATES:
        inert.state.current = runtime_state
        assert inert.owner.validate_pinned_synthetic_reflection_execution_lease(lease) is lease
        assert inert.owner.pinned_synthetic_reflection_execution_lease_state(lease) == terminal
        assert lease.fingerprint == fingerprint
        for readiness in _reads(inert, lease)[5:]:
            report = readiness()
            assert report.local_ready is report.reflection_active_ready is False
            assert report.behavioral_activation_ready is False
            assert report.reason == "PROOF_UNRESOLVED"
            assert report.readiness_reason == ("REFLECTION_LEASE_ALREADY_CONSUMED"
                if terminal == "CONSUMED" else "REFLECTION_LEASE_INVALIDATED")
    inert.state.current = "ISSUED"
    _reject(inert, lambda: _issue(inert, admission=admission), "DUPLICATE_REFLECTION_LEASE")


@pytest.mark.parametrize("runtime_state", STATES)
def test_readiness_matrix_is_immutable_report_only_and_behavior_stays_unresolved(inert, runtime_state):
    lease = _issue(inert)
    inert.state.current = runtime_state
    for required_runtime, readiness in zip(("ISSUED", "CONSUMED"), _reads(inert, lease)[5:]):
        report = readiness()
        assert report.local_ready is (runtime_state == "ISSUED")
        assert report.reflection_active_ready is (runtime_state == "CONSUMED")
        assert report.current_state == "ISSUED"
        assert report.runtime_current_state == runtime_state
        assert report.behavioral_activation_ready is False
        assert report.reason == "PROOF_UNRESOLVED"
        assert report.readiness_reason == ("PROOF_UNRESOLVED" if runtime_state == required_runtime
            else "PINNED_RUNTIME_STATE_MISMATCH")
        assert report.report_only is True
        with pytest.raises(FrozenInstanceError):
            report.behavioral_activation_ready = True
        report_dict = report.as_dict() if hasattr(report, "as_dict") else asdict(report)
        _reject(inert, lambda: inert.owner.consume_pinned_synthetic_reflection_execution_lease(report_dict),
            "REFLECTION_LEASE_UNAUTHENTICATED")


@pytest.mark.parametrize("runtime_state", ("ISSUED", "INVALIDATED"))
def test_consume_requires_current_runtime_consumed_and_preserves_issued_on_failure(inert, runtime_state):
    lease = _issue(inert)
    inert.state.current = runtime_state
    store = inert.owner._STORE
    _reject(inert, lambda: inert.owner.consume_pinned_synthetic_reflection_execution_lease(lease),
        "PINNED_RUNTIME_STATE_MISMATCH")
    assert inert.owner._STORE is store
    assert inert.owner.pinned_synthetic_reflection_execution_lease_state(lease) == "ISSUED"


@pytest.mark.parametrize("runtime_state", STATES)
def test_invalidate_accepts_any_authentic_runtime_state(inert, runtime_state):
    lease = _issue(inert)
    inert.state.current = runtime_state
    inert.owner.invalidate_pinned_synthetic_reflection_execution_lease(lease)
    assert inert.owner.pinned_synthetic_reflection_execution_lease_state(lease) == "INVALIDATED"


@pytest.mark.parametrize("first,code", (("consume", "REFLECTION_LEASE_ALREADY_CONSUMED"),
    ("invalidate", "REFLECTION_LEASE_INVALIDATED")))
def test_terminal_transitions_are_irreversible_and_repeat_rejected(inert, first, code):
    lease = _issue(inert)
    inert.state.current = "CONSUMED"
    getattr(inert.owner, first + "_pinned_synthetic_reflection_execution_lease")(lease)
    terminal = inert.owner._STORE
    for operation in ("consume", "invalidate"):
        _reject(inert, lambda operation=operation: getattr(inert.owner,
            operation + "_pinned_synthetic_reflection_execution_lease")(lease), code)
        assert inert.owner._STORE is terminal


@pytest.mark.parametrize("role", ("AFTER", "before", "exact_private_state_before", None, True, 1))
def test_mismatched_role_is_typed_and_cannot_publish(inert, role):
    admission = inert.admission()
    request = _binding(inert, admission).request
    _reject(inert, lambda: inert.owner.issue_pinned_synthetic_reflection_execution_lease(
        admission, inert.auth, inert.runtime, request, role), "REFLECTION_ROLE_MISMATCH")


@pytest.mark.parametrize("role", ("AFTER", "before", "exact_private_state_before", True, 1))
def test_optional_role_on_all_lifecycle_apis_requires_retained_semantic_role(inert, role):
    lease = _issue(inert)
    for name in API_NAMES[1:]:
        _reject(inert, lambda name=name: getattr(inert.owner, name)(lease, role=role),
            "REFLECTION_ROLE_MISMATCH")


@pytest.mark.parametrize("field,changed", (("scenario_id", "other"), ("source_sha256", "0" * 64),
    ("definition_sha256", "0" * 64), ("owner", "OtherBox"), ("member", "other"),
    ("declared_type", "long"), ("operation", "write"), ("source_kind", "caller")))
def test_authenticated_request_scope_mismatch_has_scope_category(inert, field, changed):
    admission = inert.admission()
    request = _binding(inert, admission).request
    with _edit(request, field, changed):
        _reject(inert, lambda: _issue(inert, admission=admission), "REFLECTION_SCOPE_MISMATCH")


@pytest.mark.parametrize("upstream", ("auth", "runtime"))
@pytest.mark.parametrize("field,changed", (("arguments", (True,)), ("source_size_bytes", 239.0),
    ("method_signature", "void SyntheticStateBox.decrement(int)"), ("field_type", "long")))
def test_authentic_upstream_scenarios_require_exact_scope_and_nested_types(inert, upstream, field, changed):
    admission = inert.admission()
    original = getattr(inert, upstream)
    changed_scenario = replace(original.scenario, **{field: changed})
    with _edit(original, "scenario", changed_scenario):
        _reject(inert, lambda: _issue(inert, admission=admission), "REFLECTION_SCOPE_MISMATCH")


@pytest.mark.parametrize("field,changed", (("semantic_role", "AFTER"),
    ("exact_request_observation_role", "exact_private_state_after")))
def test_authentic_admission_role_mismatch_is_not_generic_authentication(inert, field, changed):
    admission = inert.admission()
    with _edit(admission, field, changed):
        _reject(inert, lambda: _issue(inert, admission=admission), "REFLECTION_ROLE_MISMATCH")


@pytest.mark.parametrize("field,changed", (("scenario_id", "other"), ("field_name", "other"),
    ("operation", "write"), ("runtime_lease_id", "0" * 64), ("request_issuance_id", "0" * 64)))
def test_authentic_admission_projection_mismatch_has_scope_category(inert, field, changed):
    admission = inert.admission()
    with _edit(admission, field, changed):
        _reject(inert, lambda: _issue(inert, admission=admission), "REFLECTION_SCOPE_MISMATCH")


@pytest.mark.parametrize("upstream", ("admission", "request", "runtime"))
def test_scope_is_rechecked_after_issuance_before_all_reads_or_terminal_transitions(inert, upstream):
    admission = inert.admission()
    request = _binding(inert, admission).request
    lease = _issue(inert, admission=admission)
    inert.state.current = "CONSUMED"
    original, field, changed = {"admission": (admission, "field_name", "other"),
        "request": (request, "member", "other"),
        "runtime": (inert.runtime, "scenario", replace(inert.runtime.scenario, field_name="other"))}[upstream]
    store = inert.owner._STORE
    with _edit(original, field, changed):
        for operation in _operations(inert, lease):
            _reject(inert, operation, "REFLECTION_SCOPE_MISMATCH")
            assert inert.owner._STORE is store


def test_wrong_process_rejects_every_operation_before_inherited_lock(inert, monkeypatch):
    admission = inert.admission()
    lease = _issue(inert, admission=admission)
    class ForbiddenLock:
        def __enter__(self):
            raise AssertionError("wrong process reached inherited lock")
        def __exit__(self, *args):
            raise AssertionError("wrong process reached inherited lock")
    monkeypatch.setattr(inert.owner, "_LOCK", ForbiddenLock())
    monkeypatch.setattr(inert.owner.os, "getpid", lambda: inert.owner._ISSUER_PID + 1)
    for operation in (*_operations(inert, lease), lambda: _issue(inert, admission=admission)):
        _reject(inert, operation, "REFLECTION_WRONG_PROCESS")


@pytest.mark.parametrize("handle", ("admission", "auth", "runtime", "request", "lease"))
@pytest.mark.parametrize("pid_kind", ("wrong_int", "bool", "float", "integer_alias"))
def test_wrong_handle_pid_rejects_before_lock(inert, monkeypatch, handle, pid_kind):
    admission = inert.admission()
    request = _binding(inert, admission).request
    lease = _issue(inert, admission=admission)
    originals = {"admission": admission, "auth": inert.auth, "runtime": inert.runtime,
        "request": request, "lease": lease}
    class ForbiddenLock:
        def __enter__(self):
            raise AssertionError("foreign PID handle reached owner lock")
        def __exit__(self, *args):
            raise AssertionError("foreign PID handle reached owner lock")
    class IntegerAlias(int):
        pass
    monkeypatch.setattr(inert.owner, "_LOCK", ForbiddenLock())
    changed = {"wrong_int": inert.owner._ISSUER_PID + 1, "bool": True,
        "float": float(inert.owner._ISSUER_PID), "integer_alias": IntegerAlias(inert.owner._ISSUER_PID)}[pid_kind]
    operations = [lambda: inert.owner.validate_pinned_synthetic_reflection_execution_lease(
        lease, admission, inert.auth, inert.runtime, request, "BEFORE")]
    if handle == "lease":
        operations.extend(_operations(inert, lease))
    else:
        operations.append(lambda: _issue(inert, admission=admission))
    with _edit(originals[handle], "issuer_process_id" if handle == "request" else "issuing_pid", changed):
        for operation in operations:
            _reject(inert, operation, "REFLECTION_WRONG_PROCESS")


def test_final_public_runtime_check_is_last_before_publication_and_publishes_nothing_on_change(inert):
    admission = inert.admission()
    inert.calls.clear()
    inert.state.sequence[:] = ["ISSUED", "CONSUMED"]
    store = inert.owner._STORE
    _reject(inert, lambda: _issue(inert, admission=admission), "PINNED_RUNTIME_STATE_MISMATCH")
    assert inert.owner._STORE is store
    assert not store.leases and not store.admission_leases
    checks = [call for call in inert.calls if call[0] == "state"]
    assert len(checks) == 2
    assert all(call[1] is inert.runtime and call[2] is inert.auth for call in checks)
    lease = _issue(inert, admission=admission)
    inert.state.current = "INVALIDATED"
    assert inert.owner.validate_pinned_synthetic_reflection_execution_lease(lease) is lease
    assert inert.owner.check_pinned_synthetic_reflection_execution_lease_active_readiness(
        lease).reflection_active_ready is False


@pytest.mark.parametrize("failure", ("construction", "signing", "final_state"))
def test_failed_issue_preparation_never_spends_slot(inert, monkeypatch, failure):
    admission = inert.admission()
    store = inert.owner._STORE
    def unavailable(*args, **kwargs):
        raise RuntimeError("inert prepublication failure")
    if failure == "construction":
        monkeypatch.setattr(inert.owner, "_new_lease", unavailable)
    elif failure == "signing":
        monkeypatch.setattr(inert.owner, "_sign", unavailable)
    else:
        count_calls = [0]
        def state(*args, **kwargs):
            count_calls[0] += 1
            if count_calls[0] == 2:
                raise RuntimeError("inert final state failure")
            return inert.runtime_state(*args, **kwargs)
        monkeypatch.setattr(inert.runtime_owner, "pinned_synthetic_runtime_execution_lease_state", state)
    with pytest.raises((RuntimeError, inert.owner.PinnedSyntheticReflectionExecutionLeaseError)):
        _issue(inert, admission=admission)
    assert inert.owner._STORE is store
    assert not store.leases and not store.admission_leases


@pytest.mark.parametrize("transition", ("consume", "invalidate"))
def test_failed_terminal_signing_preserves_exact_prior_record(inert, transition, monkeypatch):
    lease = _issue(inert)
    inert.state.current = "CONSUMED"
    store = inert.owner._STORE
    original_sign = inert.owner._sign
    def fail_target(projection, state):
        if state != "ISSUED":
            raise RuntimeError("inert target signing failure")
        return original_sign(projection, state)
    monkeypatch.setattr(inert.owner, "_sign", fail_target)
    with pytest.raises((RuntimeError, inert.owner.PinnedSyntheticReflectionExecutionLeaseError)):
        getattr(inert.owner, transition + "_pinned_synthetic_reflection_execution_lease")(lease)
    assert inert.owner._STORE is store
    assert inert.owner.pinned_synthetic_reflection_execution_lease_state(lease) == "ISSUED"


def _race(inert, operations):
    barrier, outcomes = Barrier(len(operations)), []
    def contender(operation):
        try:
            barrier.wait(timeout=5)
            outcomes.append(("success", operation()))
        except inert.owner.PinnedSyntheticReflectionExecutionLeaseError as error:
            outcomes.append(("error", error.code))
        except BaseException as error:
            outcomes.append(("unexpected", error))
    threads = [Thread(target=contender, args=(operation,)) for operation in operations]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert len(outcomes) == len(operations)
    assert not [outcome for outcome in outcomes if outcome[0] == "unexpected"]
    return outcomes


def test_atomic_duplicate_issuance_race_has_exactly_one_publication(inert):
    admission = inert.admission()
    outcomes = _race(inert, [lambda: _issue(inert, admission=admission)] * 2)
    assert sum(kind == "success" for kind, _ in outcomes) == 1
    assert [value for kind, value in outcomes if kind == "error"] == ["DUPLICATE_REFLECTION_LEASE"]
    assert len(inert.owner._STORE.leases) == len(inert.owner._STORE.admission_leases) == 1


@pytest.mark.parametrize("operations", (("consume", "consume"), ("invalidate", "invalidate"),
    ("consume", "invalidate")))
def test_terminal_races_have_exactly_one_terminal_commit(inert, operations, monkeypatch):
    lease = _issue(inert)
    inert.state.current = "CONSUMED"
    original_store = inert.owner._STORE
    prepared_stores = []
    original_store_type = inert.owner._OwnerStore
    def track_store(*args, **kwargs):
        prepared = original_store_type(*args, **kwargs)
        prepared_stores.append(prepared)
        return prepared
    monkeypatch.setattr(inert.owner, "_OwnerStore", track_store)
    contenders = [lambda operation=operation: getattr(inert.owner,
        operation + "_pinned_synthetic_reflection_execution_lease")(lease) for operation in operations]
    outcomes = _race(inert, contenders)
    assert sum(kind == "success" for kind, _ in outcomes) == 1
    assert len(prepared_stores) == 1
    assert inert.owner._STORE is prepared_stores[0]
    terminal = inert.owner.pinned_synthetic_reflection_execution_lease_state(lease)
    assert terminal in ("CONSUMED", "INVALIDATED")
    assert [value for kind, value in outcomes if kind == "error"] == [
        "REFLECTION_LEASE_ALREADY_CONSUMED" if terminal == "CONSUMED" else "REFLECTION_LEASE_INVALIDATED"]
    assert inert.owner._STORE is not original_store
    assert original_store.leases[lease.lease_id].lifecycle_state == "ISSUED"


@pytest.mark.parametrize("kind,code,category", (
    ("auth", "pinned_synthetic_authorization_unauthenticated", "PINNED_AUTH_UNAUTHENTICATED"),
    ("auth", "pinned_synthetic_authorization_scope_mismatch", "PINNED_AUTH_SCOPE_MISMATCH"),
    ("auth", "pinned_synthetic_provider_graph_mismatch", "PINNED_PROVIDER_PROVENANCE_MISMATCH"),
    ("runtime", "LEASE_UNAUTHENTICATED", "PINNED_RUNTIME_LEASE_UNAUTHENTICATED"),
    ("runtime", "LEASE_ALREADY_CONSUMED", "PINNED_RUNTIME_STATE_MISMATCH"),
    ("runtime", "LEASE_INVALIDATED", "PINNED_RUNTIME_STATE_MISMATCH"),
    ("request", "synthetic_reflection_scope_mismatch", "REFLECTION_SCOPE_MISMATCH"),
    ("request", "synthetic_reflection_unauthenticated", "REFLECTION_REQUEST_UNAUTHENTICATED"),
    ("admission", "REFLECTION_ADMISSION_UNAUTHENTICATED", "REFLECTION_ADMISSION_UNAUTHENTICATED"),
    ("admission", "REFLECTION_ROLE_MISMATCH", "REFLECTION_ROLE_MISMATCH"),
    ("admission", "REFLECTION_SCOPE_MISMATCH", "REFLECTION_SCOPE_MISMATCH"),
))
def test_known_upstream_code_and_reason_are_preserved(inert, monkeypatch, kind, code, category):
    admission = inert.admission()
    modules = {"auth": (inert.auth_owner, "validate_pinned_synthetic_runtime_authorization",
        inert.auth_owner.PinnedSyntheticAuthorizationError),
        "runtime": (inert.runtime_owner, "validate_pinned_synthetic_runtime_execution_lease",
            inert.runtime_owner.PinnedSyntheticRuntimeExecutionLeaseError),
        "request": (inert.request_owner, "validate_synthetic_reflection_request",
            inert.request_owner.SyntheticReflectionError),
        "admission": (inert.admission_owner, "validate_pinned_synthetic_reflection_execution_admission",
            inert.admission_owner.PinnedSyntheticReflectionExecutionAdmissionError)}
    module, name, error_class = modules[kind]
    def unavailable(*args, **kwargs):
        raise error_class(code, "inert upstream reason")
    monkeypatch.setattr(module, name, unavailable)
    error = _reject(inert, lambda: _issue(inert, admission=admission), category)
    assert error.upstream_code == code
    assert error.upstream_reason == "inert upstream reason"


def test_projection_contains_no_secret_hmac_registry_or_effect_evidence(inert):
    lease = _issue(inert)
    inert.state.current = "CONSUMED"
    inert.owner.consume_pinned_synthetic_reflection_execution_lease(lease)
    report = lease.as_dict()
    dumped = json.dumps(report, sort_keys=True, allow_nan=False)
    record = inert.owner._STORE.leases[lease.lease_id]
    assert record.signature not in dumped
    assert inert.owner._SECRET.hex() not in dumped
    assert "secret" not in dumped.lower() and "registry" not in dumped.lower()
    assert "signature" not in report and "_signature" not in report
    for effect in ("read_occurred", "reflection_performed", "invocation_occurred", "scenario_executed",
            "measured_value", "actual_before", "actual_after", "effect_evidence"):
        assert effect not in report or report[effect] is False
    assert report["report_only"] is True
    assert report["behavioral_activation_ready"] is False
    assert report["consumption_proves_reflection_read"] is False
    assert report["runtime_consumption_proves_invocation"] is False
    assert all(type(getattr(lease, item.name)) in (str, int, bool, tuple) for item in fields(lease))


@pytest.mark.parametrize("terminal", (None, "CONSUMED", "INVALIDATED"))
def test_authority_never_widens_and_compilation_stays_false(inert, terminal):
    lease = _issue(inert)
    if terminal:
        inert.state.current = "CONSUMED"
        name = "consume" if terminal == "CONSUMED" else "invalidate"
        getattr(inert.owner, name + "_pinned_synthetic_reflection_execution_lease")(lease)
    for authority in FALSE_AUTHORITY:
        assert getattr(lease, authority) is False
        assert lease.as_dict()[authority] is False
    assert lease.behavioral_activation_ready is False


def test_direct_provider_or_boolean_readiness_is_never_an_api_input(inert):
    owner = inert.owner
    for name in API_NAMES:
        parameters = inspect.signature(getattr(owner, name)).parameters
        assert "provider" not in parameters
        assert not any("ready" in parameter for parameter in parameters)
    admission = inert.admission()
    with pytest.raises(TypeError):
        owner.issue_pinned_synthetic_reflection_execution_lease(admission, inert.auth,
            inert.runtime, _binding(inert, admission).request, "BEFORE", provider=inert.auth.provider)


def test_every_lease_scalar_is_authenticated(inert):
    lease = _issue(inert)
    for item in fields(lease):
        value = getattr(lease, item.name)
        changed = (not value if type(value) is bool else value + 1 if type(value) is int
            else value + ("changed",) if type(value) is tuple else value + "_changed")
        with _edit(lease, item.name, changed):
            with pytest.raises(inert.owner.PinnedSyntheticReflectionExecutionLeaseError):
                inert.owner.validate_pinned_synthetic_reflection_execution_lease(lease)


def test_current_private_state_and_record_hmac_are_authenticated(inert):
    lease = _issue(inert)
    original = inert.owner._STORE
    record = original.leases[lease.lease_id]
    for changed in (replace(record, lifecycle_state="CONSUMED"),
            replace(record, lifecycle_state="UNKNOWN"), replace(record, signature="0" * 64),
            replace(record, projection_json=record.projection_json + " ")):
        inert.owner._STORE = replace(original, leases={lease.lease_id: changed})
        _reject(inert, lambda: inert.owner.pinned_synthetic_reflection_execution_lease_state(lease),
            "REFLECTION_LEASE_UNAUTHENTICATED")
    inert.owner._STORE = original


def test_strict_canonicalization_domain_frames_public_fingerprints(inert):
    owner = inert.owner
    assert owner._canonical({"z": True, "a": [3, "int", None]}) == '{"a":[3,"int",null],"z":true}'
    for foreign in (1.0, float("nan"), (3,), {1: "key"}, SimpleNamespace(value=3)):
        with pytest.raises((TypeError, ValueError)):
            owner._canonical(foreign)
    lease = _issue(inert)
    unsigned = lease.as_dict()
    for name in ("report_only", "current_state", "runtime_current_state"):
        unsigned.pop(name, None)
    unsigned.pop("stable_fingerprint")
    assert lease.stable_fingerprint == _framed_digest(owner._DOMAIN, "lease-fingerprint", unsigned)
    unsigned.pop("evidence_digest")
    assert lease.evidence_digest == _framed_digest(owner._DOMAIN, "lease-evidence", unsigned)

