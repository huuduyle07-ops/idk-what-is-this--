"""EXECUTOR.1: authorization-first, fail-closed diagnostic execution boundary.

The frozen effect contract requires technical prevention of candidate network,
filesystem, environment and extra-process effects. No verified candidate sandbox
adapter exists here. A temporary cwd is insufficient. Until that boundary exists,
this consumer issues only authenticated *blocked* receipts and launches nothing.
No dormant unsandboxed runner or generic harness renderer is exposed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import hmac
import json
import secrets
from time import perf_counter

from core import behavioral_evidence_execution_plan as planner
from core import read_only_reflection as reflection
from core import runtime_diagnostic_authorization as authorization_owner

PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1"
SCHEMA_VERSION = "patch_candidate_behavior_executor_1_v1"
EXECUTOR_ID = "authorization_first_bounded_java_diagnostic_executor_v1"
FIRST_REMAINING_BLOCKER = "runtime_executor_capability_incomplete"
MAX_RECEIPT_BYTES = 512_000
TIMING_FIELDS = ("authorization_reconstruction_seconds", "virtual_byte_projection_seconds",
    "harness_rendering_seconds", "harness_compile_seconds", "jvm_startup_seconds",
    "scenario_execution_seconds", "reflection_observations_seconds",
    "receipt_normalization_seconds", "cleanup_seconds", "total_seconds")
_RECEIPT_SECRET = secrets.token_bytes(32)
_LINEAGE = ("execution_plan_fingerprint", "behavioral_spec_fingerprint",
    "materialization_fingerprint", "candidate_fingerprint", "compile_receipt_fingerprint",
    "repository_id", "repository_evidence_fingerprint")
_BLOCKED_STATUSES = frozenset({"diagnostic_execution_authority_missing",
    "runtime_executor_console_unavailable", FIRST_REMAINING_BLOCKER})


class BehavioralDiagnosticExecutionError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        self.java_execution_count = 0
        self.javac_calls = 0
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise BehavioralDiagnosticExecutionError(code, reason)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class BoundedJavaDiagnosticExecutorDescriptor:
    """Trusted implementation facts, never an authorization or caller setting."""
    executor_identity: str = field(default=EXECUTOR_ID, init=False)
    capability: str = field(default="bounded_java_diagnostic_executor", init=False)
    status: str = field(default=FIRST_REMAINING_BLOCKER, init=False)
    runtime_executor_available: bool = field(default=False, init=False)
    minimum_runtime_boundary_enforced: bool = field(default=False, init=False)
    console: bool = field(default=False, init=False)
    arbitrary_command: bool = field(default=False, init=False)
    shell: bool = field(default=False, init=False)
    reflection_read_only: bool = field(default=True, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    network_isolation_enforced: bool = field(default=False, init=False)
    filesystem_isolation_enforced: bool = field(default=False, init=False)
    environment_isolation_enforced: bool = field(default=False, init=False)
    child_process_isolation_enforced: bool = field(default=False, init=False)
    network_isolation_status: str = field(default="network_isolation_unavailable", init=False)
    filesystem_isolation_status: str = field(default="filesystem_isolation_unavailable", init=False)
    enforcement_status: str = field(default="no_verified_candidate_runtime_sandbox_adapter", init=False)
    unavailable_requirements: tuple[str, ...] = field(default=(
        "ephemeral_working_directory", "fixed_executable_and_arguments", "exact_source_and_classpath",
        "hard_wall_clock_timeout", "hard_stdout_stderr_bounds", "all_child_process_cleanup",
        "no_persistent_diagnostic_artifacts", "candidate_filesystem_isolation",
        "candidate_network_isolation", "candidate_environment_isolation",
        "candidate_extra_process_prevention"), init=False)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "executor_descriptor_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def get_bounded_java_diagnostic_executor_descriptor():
    # Presence of Java, a temp directory, or caller assertions cannot enable it.
    return BoundedJavaDiagnosticExecutorDescriptor()


@dataclass(frozen=True, slots=True)
class VirtualProductInput:
    path: str
    sha256: str
    size_bytes: int
    provenance: str


@dataclass(frozen=True, slots=True)
class BehavioralDiagnosticExecutionReceipt:
    """Immutable raw execution evidence; V1 currently admits blocked facts only.

    No observations can be minted while the mandatory boundary is unavailable.
    The private process-local signature is deliberately omitted from reports.
    """
    status: str
    runtime_authorization_fingerprint: str
    execution_plan_fingerprint: str
    behavioral_spec_fingerprint: str
    materialization_fingerprint: str
    candidate_fingerprint: str
    compile_receipt_fingerprint: str
    repository_id: str
    repository_evidence_fingerprint: str
    scenario_id: str
    authorization_source_synthetic: bool
    authorization_source_fingerprint: str
    input_manifest: tuple[VirtualProductInput, ...]
    constructor_target: planner.ExactMemberBinding | None
    constructor_arguments: tuple[planner.FixtureArgument, ...]
    setup_invocations: tuple[planner.PlannedInvocation, ...]
    action_invocation: planner.PlannedInvocation | None
    observation_targets: tuple[planner.PlannedObservation, ...]
    reflection_requests: tuple[reflection.ReadOnlyReflectionRequest, ...]
    executor_descriptor: BoundedJavaDiagnosticExecutorDescriptor
    _signature: str = field(default="", repr=False, compare=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    authority: str = field(default="diagnostic_runtime_evidence_only", init=False)
    execution_completed: bool = field(default=False, init=False)
    execution_ready: bool = field(default=False, init=False)
    execution_attempted: bool = field(default=False, init=False)
    runtime_executor_available: bool = field(default=False, init=False)
    harness_sha256: str = field(default="", init=False)
    constructor_result: None = field(default=None, init=False)
    setup_invocation_results: tuple = field(default=(), init=False)
    action_invocation_result: None = field(default=None, init=False)
    direct_return_observations: tuple = field(default=(), init=False)
    reflection_observations: tuple = field(default=(), init=False)
    stdout_metadata: None = field(default=None, init=False)
    stderr_metadata: None = field(default=None, init=False)
    process_exit_status: None = field(default=None, init=False)
    compiler_identity: None = field(default=None, init=False)
    jvm_identity: None = field(default=None, init=False)
    workspace_created: bool = field(default=False, init=False)
    virtual_bytes_projected: bool = field(default=False, init=False)
    workspace_integrity_status: str = field(default="not_projected_execution_blocked", init=False)
    cleanup_status: str = field(default="not_required_no_runtime_resources_created", init=False)
    provenance: str = field(default="process_local_executor_blocked_decision", init=False)
    write_authority: bool = field(default=False, init=False)
    product_write_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    reflection_write_authority: bool = field(default=False, init=False)
    test_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    java_execution_count: int = field(default=0, init=False)
    javac_calls: int = field(default=0, init=False)
    reflection_execution_count: int = field(default=0, init=False)
    diagnostic_harness_generation_count: int = field(default=0, init=False)
    console_open_count: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    source_mutation: int = field(default=0, init=False)
    test_generation_count: int = field(default=0, init=False)

    def __post_init__(self):
        try:
            planner._immutable(self)
        except planner.BehavioralExecutionPlanError:
            _fail("executor_receipt_invalid", "recursively immutable evidence required")
        if self.status not in _BLOCKED_STATUSES:
            _fail("executor_receipt_invalid", "no verified runtime execution boundary")
        for name, kind in (("input_manifest", VirtualProductInput),
                ("constructor_arguments", planner.FixtureArgument),
                ("setup_invocations", planner.PlannedInvocation),
                ("observation_targets", planner.PlannedObservation),
                ("reflection_requests", reflection.ReadOnlyReflectionRequest)):
            rows = getattr(self, name)
            if type(rows) is not tuple or len(rows) > planner.MAX_ITEMS or any(type(r) is not kind for r in rows):
                _fail("executor_receipt_invalid", "bounded exact typed records required")
        if type(self.executor_descriptor) is not BoundedJavaDiagnosticExecutorDescriptor:
            _fail("executor_receipt_invalid", "trusted executor descriptor required")

    def _semantic_payload(self):
        payload = asdict(self)
        payload.pop("_signature")
        return payload

    @property
    def fingerprint(self):
        return _hash(self._semantic_payload())

    @property
    def execution_receipt_fingerprint(self):
        return self.fingerprint

    def as_dict(self):
        return {**json.loads(_json(self._semantic_payload())), "execution_receipt_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _gate(authorization, scenario_id, parents, measured):
    if (type(authorization) is not authorization_owner.RuntimeDiagnosticAuthorization
            or type(scenario_id) is not str or not scenario_id or len(scenario_id) > 160):
        _fail("executor_authorization_missing", "fresh exact typed runtime authorization required")
    tick = perf_counter()
    try:
        checked = authorization_owner.validate_runtime_diagnostic_authorization(authorization, **parents)
    except authorization_owner.RuntimeDiagnosticAuthorizationError as exc:
        _fail("executor_authorization_missing", exc.code + ": " + exc.reason)
    finally:
        measured["authorization_reconstruction_seconds"] += perf_counter() - tick
    row = next((r for r in checked.scenarios if r.scenario_id == scenario_id), None)
    if row is None:
        _fail("executor_authorization_missing", "scenario outside fresh exact execution plan")
    if not row.policy_authorized:
        # This includes real BANK and direct-only lineages without a source.
        return checked, row.scenario, "diagnostic_execution_authority_missing"
    if scenario_id not in checked.authorized_scenario_ids:
        _fail("executor_authorization_missing", "scenario outside exact authorization")
    scenario = row.scenario
    if ("deterministic_console_input" in scenario.required_capabilities
            or any(i.console_input is not None for i in (*scenario.setup_invocations,
                *((scenario.invocation,) if scenario.invocation else ())))):
        return checked, scenario, "runtime_executor_console_unavailable"
    if (checked.authorization_source_synthetic is not True
            or not row.capability_available
            or get_bounded_java_diagnostic_executor_descriptor().runtime_executor_available is not True):
        return checked, scenario, FIRST_REMAINING_BLOCKER
    # There is deliberately no fallback process-launch path, even if the
    # reporting descriptor is accidentally replaced or its flag is tampered.
    return checked, scenario, FIRST_REMAINING_BLOCKER


def _blocked_facts(authorization, scenario, status, materialized):
    # Only exact supplied virtual bytes; no repository discovery, source
    # regeneration, workspace construction, tool resolution or compilation.
    inputs = tuple(VirtualProductInput(f.path, sha256(f.after_bytes).hexdigest(),
        len(f.after_bytes), "materialized_virtual_file") for f in materialized.virtual_files)
    if any(i.sha256 != f.after_sha256 for i, f in zip(inputs, materialized.virtual_files)):
        _fail("executor_authorization_missing", "exact virtual source digest mismatch")
    dependencies = tuple(VirtualProductInput(f.path, f.source_sha256, f.source_size,
        "bound_supporting_file_not_projected") for f in materialized.supporting_files)
    return BehavioralDiagnosticExecutionReceipt(status=status,
        runtime_authorization_fingerprint=authorization.fingerprint,
        **{name: getattr(authorization, name) for name in _LINEAGE},
        scenario_id=scenario.scenario_id,
        authorization_source_synthetic=authorization.authorization_source_synthetic,
        authorization_source_fingerprint=authorization.authorization_source_fingerprint,
        input_manifest=tuple(sorted((*inputs, *dependencies), key=lambda i: i.path)),
        constructor_target=scenario.constructor, constructor_arguments=scenario.constructor_arguments,
        setup_invocations=scenario.setup_invocations, action_invocation=scenario.invocation,
        observation_targets=scenario.observations,
        reflection_requests=tuple(r for r in authorization.authorized_reflection_requests
            if r.scenario_id == scenario.scenario_id),
        executor_descriptor=get_bounded_java_diagnostic_executor_descriptor())


def _signature(receipt):
    return hmac.new(_RECEIPT_SECRET, receipt.to_json().encode("utf-8"), sha256).hexdigest()


def _parents(execution_plan, specification, compile_receipt, materialized, candidate,
        admitted_scope, authorization_source, behavioral_admission, reflection_descriptor,
        reflection_requests, fresh_inputs):
    return dict(execution_plan=execution_plan, specification=specification,
        compile_receipt=compile_receipt, materialized=materialized, candidate=candidate,
        admitted_scope=admitted_scope, authorization_source=authorization_source,
        behavioral_admission=behavioral_admission, reflection_descriptor=reflection_descriptor,
        reflection_requests=reflection_requests, **fresh_inputs)


def execute_behavioral_diagnostic(authorization, *, scenario_id, execution_plan, specification,
        compile_receipt, materialized, candidate, admitted_scope, authorization_source=None,
        behavioral_admission=None, reflection_descriptor=authorization_owner._LOCAL_REFLECTION,
        reflection_requests=(), timings=None, **fresh_inputs):
    """Validate exact authority, then stop before every runtime effect.

    The user-specified capability-incomplete stop condition is mandatory. This
    function cannot authorize execution, generate a harness or launch Java.
    Timings report zero for stages never entered, including compile/startup.
    """
    measured = {} if timings is None else timings
    measured.update({key: 0.0 for key in TIMING_FIELDS})
    began = perf_counter()
    try:
        parents = _parents(execution_plan, specification, compile_receipt, materialized,
            candidate, admitted_scope, authorization_source, behavioral_admission,
            reflection_descriptor, reflection_requests, fresh_inputs)
        checked, scenario, status = _gate(authorization, scenario_id, parents, measured)
        tick = perf_counter()
        receipt = _blocked_facts(checked, scenario, status, materialized)
        if len(receipt.to_json().encode("utf-8")) > MAX_RECEIPT_BYTES:
            _fail("executor_receipt_invalid", "receipt byte bound")
        object.__setattr__(receipt, "_signature", _signature(receipt))
        measured["receipt_normalization_seconds"] += perf_counter() - tick
        return receipt
    except BehavioralDiagnosticExecutionError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        _fail("executor_authorization_missing", type(exc).__name__)
    finally:
        measured["total_seconds"] = perf_counter() - began


def validate_behavioral_diagnostic_execution_receipt(receipt, *, authorization, scenario_id,
        execution_plan, specification, compile_receipt, materialized, candidate, admitted_scope,
        authorization_source=None, behavioral_admission=None,
        reflection_descriptor=authorization_owner._LOCAL_REFLECTION, reflection_requests=(),
        **fresh_inputs):
    """Pure authenticated validation; caller JSON cannot establish runtime facts.

    This validates the currently issued blocked schema only. No reflection
    observations or successful execution receipts can be issued by this phase
    while candidate isolation is unavailable. Freshness is exact structural
    lineage, never a duration, timestamp or temporary path.
    """
    try:
        if type(receipt) is not BehavioralDiagnosticExecutionReceipt:
            _fail("executor_receipt_unauthenticated", "exported JSON is report-only")
        receipt.__post_init__()
        if (type(receipt._signature) is not str or not receipt._signature
                or len(receipt.to_json().encode("utf-8")) > MAX_RECEIPT_BYTES
                or not hmac.compare_digest(receipt._signature, _signature(receipt))):
            _fail("executor_receipt_unauthenticated", "executor-local issuance absent or altered")
        parents = _parents(execution_plan, specification, compile_receipt, materialized,
            candidate, admitted_scope, authorization_source, behavioral_admission,
            reflection_descriptor, reflection_requests, fresh_inputs)
        checked, scenario, status = _gate(authorization, scenario_id, parents,
            {key: 0.0 for key in TIMING_FIELDS})
        expected = _blocked_facts(checked, scenario, status, materialized)
        if receipt.to_json() != expected.to_json():
            _fail("executor_receipt_stale", "fresh exact bindings or blocked execution facts differ")
        return receipt
    except BehavioralDiagnosticExecutionError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        _fail("executor_receipt_invalid", type(exc).__name__)
