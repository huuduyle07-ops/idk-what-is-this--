"""Pure, exact behavioral admission; available mechanisms are not permission.

Frozen evidence requirements authorize no runtime diagnostic adapter today.
Keep capability-ready scenarios distinct from execution-admitted scenarios;
never turn a planned need, serialized descriptor or compiler receipt into a
Java execution grant. This owner consumes only supplied exact lineage buffers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from hashlib import sha256
import json
import math
from time import perf_counter

from core import behavioral_evidence_execution_plan as planner
from core import read_only_reflection as reflection
from core.acquisition_request import acquisition_authority
from web import preflight_request as diagnostic_policy

PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1"
SCHEMA_VERSION = "patch_candidate_behavior_exec_admit_1_v1"
FIRST_REMAINING_BLOCKER = "diagnostic_execution_authority_missing"
TIMING_FIELDS = ("execution_plan_reconstruction_seconds", "evidence_authority_validation_seconds",
    "capability_descriptor_reconstruction_seconds", "reflection_request_reconstruction_seconds",
    "scenario_admission_classification_seconds", "coverage_projection_seconds",
    "admission_fingerprinting_seconds", "total_seconds")
SCENARIO_STATUSES = frozenset({"admitted", "blocked_missing_capability", "blocked_authority",
    "blocked_stale", "blocked_semantic_gap", "static_not_executed"})
MAX_ADMISSION_BYTES = 512_000
_LOCAL_REFLECTION = object()
_FALSE_AUTHORITIES = planner.AUTHORITY_KEYS | frozenset({"product_write_authority",
    "repository_write_authority", "reflection_write_authority", "network_authorized",
    "arbitrary_shell_authority", "candidate_revision_authority", "reflection_authorized",
    "behavioral_execution_admitted", "execution_completed", "behavior_validated",
    "correctness_proven", "write", "apply", "test_write", "reflection_write",
    "diagnostic_execution_permitted", "scenario_eligible_for_diagnostic_execution"})
_FORBIDDEN = planner.FORBIDDEN_PAYLOAD_KEYS | frozenset({"argv", "shell", "command_string",
    "java", "javac", "powershell", "bash", "cmd.exe", "executor_token", "runtime_object",
    "adapter_receipt", "proposed_test_file_admission"})
_LINEAGE = ("task_fingerprint", "effective_design_fingerprint", "implementation_plan_fingerprint",
    "candidate_fingerprint", "materialization_fingerprint", "compile_receipt_fingerprint",
    "behavioral_spec_fingerprint")


class BehavioralExecutionAdmissionError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise BehavioralExecutionAdmissionError(code, reason)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _rows(value, kind):
    if type(value) is not tuple or len(value) > planner.MAX_ITEMS or any(type(x) is not kind for x in value):
        _fail("admission_invalid", "bounded closed typed tuple required")


def _immutable(value):
    try:
        planner._immutable(value)
    except planner.BehavioralExecutionPlanError:
        _fail("admission_invalid", "bounded recursively immutable evidence required")


@dataclass(frozen=True, slots=True)
class DiagnosticCapabilityDescriptor:
    capability: str
    operation: str
    availability: str
    exact_targets: tuple[planner.ExactMemberBinding, ...]
    reflection_descriptor_fingerprint: str = ""
    execution_authorized: bool = field(default=False, init=False)
    write_authority: bool = field(default=False, init=False)

    def __post_init__(self):
        _immutable(self)
        _rows(self.exact_targets, planner.ExactMemberBinding)
        if self.capability not in planner.CAPABILITIES:
            _fail("admission_invalid", "closed capability required")

    @property
    def fingerprint(self):
        return _hash(asdict(self))


@dataclass(frozen=True, slots=True)
class DiagnosticEvidenceAuthority:
    evidence_requirement_fingerprint: str
    policy_fingerprint: str
    behavioral_need_fingerprints: tuple[str, ...]
    source: str = field(default="PREFLIGHT.REQUEST.1/ACQUIRE.1", init=False)
    diagnostic_kind: str = field(default="runtime_evidence", init=False)
    diagnostic_execution_permitted: bool = field(default=False, init=False)
    status: str = field(default="diagnostic_execution_authority_missing", init=False)

    def __post_init__(self):
        _immutable(self)
        _rows(self.behavioral_need_fingerprints, str)


@dataclass(frozen=True, slots=True)
class RuntimeIsolationRequirements:
    """Required future enforcement, not a claim that an executor exists."""
    ephemeral_workspace_required: bool = field(default=True, init=False)
    exact_virtual_candidate_bytes_required: bool = field(default=True, init=False)
    fresh_candidate_instance_required: bool = field(default=True, init=False)
    repository_source_write_forbidden: bool = field(default=True, init=False)
    wall_clock_timeout_seconds: float = field(default=diagnostic_policy.DiagnosticLimits().process_timeout_seconds, init=False)
    stdout_limit_bytes: int = field(default=diagnostic_policy.DiagnosticLimits().max_output_bytes, init=False)
    stderr_limit_bytes: int = field(default=diagnostic_policy.DiagnosticLimits().max_output_bytes, init=False)
    child_process_cleanup_required: bool = field(default=True, init=False)
    arbitrary_command_surface_forbidden: bool = field(default=True, init=False)
    persistent_diagnostic_artifacts_forbidden: bool = field(default=True, init=False)
    network_capability: bool = field(default=False, init=False)
    filesystem_persistence_authority: bool = field(default=False, init=False)
    minimum_runtime_boundary_enforced: bool = field(default=False, init=False)
    hard_network_isolation_available: bool = field(default=False, init=False)
    hard_filesystem_isolation_available: bool = field(default=False, init=False)
    executor_status: str = field(default="runtime_executor_capability_missing", init=False)

    def __post_init__(self):
        _immutable(self)


@dataclass(frozen=True, slots=True)
class ScenarioAdmission:
    scenario_id: str
    status: str
    reasons: tuple[str, ...]
    capability_eligible: bool
    scenario: planner.DiagnosticScenario
    reflection_requests: tuple[reflection.ReadOnlyReflectionRequest, ...]
    capability_descriptor_fingerprints: tuple[str, ...]
    isolation_requirements: RuntimeIsolationRequirements
    scenario_eligible_for_diagnostic_execution: bool = field(default=False, init=False)
    process_local_authenticated_reflection_receipt_required: bool = field(default=True, init=False)
    candidate_runtime_receipt_issuance_available: bool = field(default=False, init=False)

    def __post_init__(self):
        _immutable(self)
        _rows(self.reasons, str)
        _rows(self.reflection_requests, reflection.ReadOnlyReflectionRequest)
        _rows(self.capability_descriptor_fingerprints, str)
        if (self.status not in SCENARIO_STATUSES or type(self.scenario) is not planner.DiagnosticScenario
                or self.scenario_id != self.scenario.scenario_id
                or type(self.capability_eligible) is not bool
                or type(self.isolation_requirements) is not RuntimeIsolationRequirements):
            _fail("admission_invalid", "exact typed scenario decision required")

    @property
    def reflection_request_fingerprints(self):
        return tuple(request.fingerprint for request in self.reflection_requests)


@dataclass(frozen=True, slots=True)
class ObligationAdmissionCoverage:
    obligation_id: str
    status: str
    admitted_scenario_ids: tuple[str, ...]
    blocked_scenario_ids: tuple[str, ...]
    evidence_status: str

    def __post_init__(self):
        _immutable(self)
        _rows(self.admitted_scenario_ids, str)
        _rows(self.blocked_scenario_ids, str)
        if self.status not in {"static_not_executed", "admitted_runtime_evidence",
                "partial_runtime_evidence", "blocked_runtime_evidence"}:
            _fail("admission_invalid", "closed coverage required")


@dataclass(frozen=True, slots=True)
class BehavioralExecutionAdmission:
    execution_plan_fingerprint: str
    task_fingerprint: str
    effective_design_fingerprint: str
    implementation_plan_fingerprint: str
    scope_admission_fingerprint: str
    candidate_fingerprint: str
    materialization_fingerprint: str
    compile_receipt_fingerprint: str
    behavioral_spec_fingerprint: str
    evidence_requirement_fingerprint: str
    repository_id: str
    repository_evidence_fingerprint: str
    evidence_authority: DiagnosticEvidenceAuthority
    capability_descriptors: tuple[DiagnosticCapabilityDescriptor, ...]
    reflection_descriptor: reflection.ReadOnlyReflectionCapabilityDescriptor | None
    admitted_scenarios: tuple[ScenarioAdmission, ...]
    blocked_scenarios: tuple[ScenarioAdmission, ...]
    admitted_invocation_targets: tuple[planner.ExactMemberBinding, ...]
    admitted_observation_requests: tuple[planner.PlannedObservation, ...]
    admitted_reflection_requests: tuple[reflection.ReadOnlyReflectionRequest, ...]
    admitted_capability_descriptors: tuple[DiagnosticCapabilityDescriptor, ...]
    coverage: tuple[ObligationAdmissionCoverage, ...]
    static_satisfied_obligations: tuple[str, ...]
    implementation_calculations: tuple[planner.oracle.AdmittedInterestCalculation, ...]
    status: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    scope_authority: str = field(default="diagnostic_behavioral_execution_only", init=False)
    behavioral_execution_admitted: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    java_execution_authorized: bool = field(default=False, init=False)
    reflection_authorized: bool = field(default=False, init=False)
    console_authorized: bool = field(default=False, init=False)
    diagnostic_harness_generation_authorized: bool = field(default=False, init=False)
    write_authority: bool = field(default=False, init=False)
    product_write_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    candidate_revision_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    test_write_authority: bool = field(default=False, init=False)
    reflection_write_authority: bool = field(default=False, init=False)
    network_authorized: bool = field(default=False, init=False)
    arbitrary_shell_authority: bool = field(default=False, init=False)
    test_file_handling: str = field(default="proposed_test_file_only", init=False)
    process_local_authenticated_reflection_receipt_required: bool = field(default=True, init=False)
    runtime_executor_status: str = field(default="runtime_executor_capability_missing", init=False)
    execution_completed: bool = field(default=False, init=False)
    behavior_validated: bool = field(default=False, init=False)
    correctness_proven: bool = field(default=False, init=False)
    java_execution_count: int = field(default=0, init=False)
    reflection_execution_count: int = field(default=0, init=False)
    console_open_count: int = field(default=0, init=False)
    javac_calls: int = field(default=0, init=False)
    command_execution_count: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    source_mutation: int = field(default=0, init=False)
    diagnostic_harness_generation_count: int = field(default=0, init=False)
    test_generation_count: int = field(default=0, init=False)
    first_remaining_blocker: str = field(default=FIRST_REMAINING_BLOCKER, init=False)

    def __post_init__(self):
        _immutable(self)
        for name, kind in (("capability_descriptors", DiagnosticCapabilityDescriptor),
                ("admitted_scenarios", ScenarioAdmission), ("blocked_scenarios", ScenarioAdmission),
                ("admitted_invocation_targets", planner.ExactMemberBinding),
                ("admitted_observation_requests", planner.PlannedObservation),
                ("admitted_reflection_requests", reflection.ReadOnlyReflectionRequest),
                ("admitted_capability_descriptors", DiagnosticCapabilityDescriptor),
                ("coverage", ObligationAdmissionCoverage), ("static_satisfied_obligations", str),
                ("implementation_calculations", planner.oracle.AdmittedInterestCalculation)):
            _rows(getattr(self, name), kind)
        if (type(self.evidence_authority) is not DiagnosticEvidenceAuthority
                or type(self.reflection_descriptor) not in {type(None), reflection.ReadOnlyReflectionCapabilityDescriptor}
                or self.status != "admission_authority_incomplete"):
            _fail("admission_invalid", "closed current authority classification required")

    @property
    def scenarios(self):
        return self.admitted_scenarios + self.blocked_scenarios

    @property
    def capability_eligible_scenario_ids(self):
        return tuple(row.scenario_id for row in self.scenarios if row.capability_eligible)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    @property
    def admission_fingerprint(self):
        return self.fingerprint

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "admission_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _payload_gate(value, depth=0):
    if depth > 32:
        _fail("admission_invalid", "nesting bound")
    if type(value) is dict:
        if len(value) > 96:
            _fail("admission_invalid", "record bound")
        for key, item in value.items():
            if type(key) is not str:
                _fail("admission_invalid", "closed string keys required")
            if key in _FALSE_AUTHORITIES and item is not False:
                _fail("admission_authority_escalation", key)
            if key in _FORBIDDEN:
                _fail("admission_invalid", "no executable payload or command surface")
            if key == "scope_authority" and item != "diagnostic_behavioral_execution_only":
                _fail("admission_authority_escalation", key)
            _payload_gate(item, depth + 1)
    elif type(value) in {tuple, list}:
        if len(value) > planner.MAX_ITEMS:
            _fail("admission_invalid", "collection bound")
        for item in value:
            _payload_gate(item, depth + 1)
    elif value is not None and (type(value) not in {str, bool, int, float}
            or (type(value) is float and not math.isfinite(value))
            or (type(value) is str and len(value) > 4096)):
        _fail("admission_invalid", "bounded scalar required")


def _authority(scope, spec):
    """Typed requirements bind the question; frozen owners decide permission.

    The current policy implements compile_evidence only. Do not manufacture a
    CONTROL bootstrap scope, register a runtime adapter, or treat an acquisition
    requirement as a grant. Changing this decision requires a later authority
    phase; it is not a caller option on this pure owner.
    """
    needs = tuple(n for n in scope.validation_evidence_needs
        if n.kind in {"focused_behavioral_test", "validation_evidence_need"})
    requirements = _hash({"scope_admission_fingerprint": scope.fingerprint,
        "validation_evidence_needs": [asdict(n) for n in needs],
        "behavioral_evidence_requirements": [asdict(n) for n in spec.evidence_requirements]})
    policy = _hash({"acquisition_authority": acquisition_authority(),
        "diagnostic_authority": dict(diagnostic_policy.AUTHORITY),
        "diagnostic_adapters": sorted((kind, language, adapter)
            for (kind, language), adapter in diagnostic_policy.ADAPTER_REGISTRY.items()),
        "runtime_permission": "not_granted_by_frozen_evidence_contracts"})
    return DiagnosticEvidenceAuthority(requirements, policy, tuple(_hash(asdict(n)) for n in needs))


def _unique_targets(values):
    return tuple(sorted(set(values), key=lambda target: _json(asdict(target))))


def _capabilities(plan, descriptor, materialized, inputs):
    """Use canonical bound operations, never serialized capability labels."""
    invocations = _unique_targets(target for scenario in plan.scenarios
        for target in ([scenario.constructor] if scenario.constructor else []) +
            [call.target for call in (*scenario.setup_invocations,
                *((scenario.invocation,) if scenario.invocation else ()))])
    inventory = planner._inventory(materialized, inputs)
    exact_queries = _unique_targets(observation.target for scenario in plan.scenarios
        for observation in scenario.observations if observation.mechanism == "existing_exact_state_query")
    public_targets = _unique_targets(target for target in (*invocations, *exact_queries)
        if planner._access(target, inventory) == "direct_public_invocation")
    package_targets = _unique_targets((*[target for target in (*invocations, *exact_queries)
        if planner._access(target, inventory) == "existing_package_access"],
        *[observation.target for scenario in plan.scenarios for observation in scenario.observations
            if "existing_package_access" in observation.required_capabilities and observation.target]))
    returns = _unique_targets((*[observation.target for scenario in plan.scenarios
        for observation in scenario.observations if observation.mechanism == "direct_return"],
        *[call.target for scenario in plan.scenarios for call in scenario.setup_invocations
            if call.expected_setup_return is not None]))
    states = _unique_targets(observation.target for scenario in plan.scenarios
        for observation in scenario.observations
        if observation.mechanism in {"direct_state_access", "existing_exact_state_query"})
    reflection_targets = _unique_targets(observation.target for scenario in plan.scenarios
        for observation in scenario.observations if observation.mechanism == "read_only_reflection")
    required = sorted({cap for scenario in plan.scenarios for cap in scenario.required_capabilities})
    rows = []
    for capability in required:
        if capability == "read_only_reflection":
            rows.append(DiagnosticCapabilityDescriptor(capability, "read_exact_bound_field",
                descriptor.availability if descriptor else "unavailable", reflection_targets,
                descriptor.fingerprint if descriptor else ""))
        elif capability == "deterministic_console_input":
            rows.append(DiagnosticCapabilityDescriptor(capability, "deterministic_console_attachment",
                "unavailable", ()))
        elif capability in {"unsupported_observation", "execution_setup_unavailable"}:
            rows.append(DiagnosticCapabilityDescriptor(capability, "unsupported",
                "unavailable", ()))
        else:
            targets = returns if capability == "direct_return_observation" else states if capability == "direct_state_observation" else package_targets if capability == "existing_package_access" else public_targets
            operation = "capture_exact_direct_return" if capability == "direct_return_observation" else "read_exact_bound_surface" if capability == "direct_state_observation" else "access_exact_plan_bound_surface" if capability == "existing_package_access" else "invoke_exact_plan_bound_surface"
            rows.append(DiagnosticCapabilityDescriptor(capability, operation,
                "available_by_existing_surface", targets))
    return tuple(rows)


def _run(execution_plan, specification, compile_receipt, materialized, candidate,
        admitted_scope, reflection_descriptor, inputs, measured):
    if "repository_root" in inputs:
        _fail("admission_invalid", "only supplied exact lineage buffers are consumed")
    tick = perf_counter()
    try:
        plan = planner.validate_behavioral_evidence_execution_plan(execution_plan,
            specification=specification, compile_receipt=compile_receipt, materialized=materialized,
            candidate=candidate, admitted_scope=admitted_scope, **inputs)
        spec = planner.oracle.validate_behavioral_validation_specification(specification,
            compile_receipt=compile_receipt, materialized=materialized, candidate=candidate,
            admitted_scope=admitted_scope, **inputs)
    except (planner.BehavioralExecutionPlanError, planner.oracle.BehavioralSpecificationError) as exc:
        _fail("admission_stale", exc.code + ": " + exc.reason)
    finally:
        measured["execution_plan_reconstruction_seconds"] += perf_counter() - tick
    tick = perf_counter()
    authority = _authority(admitted_scope, spec)
    measured["evidence_authority_validation_seconds"] += perf_counter() - tick
    tick = perf_counter()
    descriptor = None
    if reflection_descriptor is not None:
        local = reflection.get_read_only_reflection_capability_descriptor()
        if reflection_descriptor is not _LOCAL_REFLECTION:
            if type(reflection_descriptor) is not reflection.ReadOnlyReflectionCapabilityDescriptor:
                _fail("admission_invalid", "caller-authored descriptor JSON is not authority")
            try:
                reflection.validate_read_only_reflection_capability_descriptor(reflection_descriptor)
            except reflection.ReadOnlyReflectionError as exc:
                _fail("admission_authority_escalation", exc.code)
        descriptor = reflection.validate_read_only_reflection_capability_descriptor(local)
    capabilities = _capabilities(plan, descriptor, materialized, inputs)
    by_capability = {row.capability: row for row in capabilities}
    measured["capability_descriptor_reconstruction_seconds"] += perf_counter() - tick
    decisions = []
    for scenario in plan.scenarios:
        tick = perf_counter()
        missing = tuple(c for c in scenario.required_capabilities
            if by_capability[c].availability not in {"available_by_existing_surface", "available_but_not_execution_admitted"})
        gaps = tuple(gap.semantic_dimension for gap in plan.human_semantic_blockers
            if any(obligation.oracle.semantic_dimension == gap.semantic_dimension
                for obligation in plan.obligations if obligation.obligation_id in scenario.obligation_ids))
        capable = not missing and not gaps
        status = "blocked_semantic_gap" if gaps else "blocked_missing_capability" if missing else "blocked_authority"
        reasons = gaps or missing or ("diagnostic_execution_authority_missing",)
        fingerprints = tuple(by_capability[c].fingerprint for c in scenario.required_capabilities)
        measured["scenario_admission_classification_seconds"] += perf_counter() - tick
        tick = perf_counter()
        requests = []
        if capable:
            for observation in scenario.observations:
                if observation.mechanism == "read_only_reflection":
                    try:
                        requests.append(reflection.build_read_only_reflection_request(plan,
                            scenario_id=scenario.scenario_id, observation_id=observation.observation_id,
                            specification=spec, compile_receipt=compile_receipt, materialized=materialized,
                            candidate=candidate, admitted_scope=admitted_scope, **inputs))
                    except reflection.ReadOnlyReflectionError as exc:
                        _fail("admission_stale", exc.code + ": " + exc.reason)
        measured["reflection_request_reconstruction_seconds"] += perf_counter() - tick
        decisions.append(ScenarioAdmission(scenario.scenario_id, status, reasons, capable, scenario,
            tuple(requests), fingerprints, RuntimeIsolationRequirements()))
    tick = perf_counter()
    coverage = []
    for obligation in plan.obligations:
        selected = tuple(row for row in decisions if obligation.obligation_id in row.scenario.obligation_ids)
        static = obligation.evidence_mode == "static_already_satisfied"
        coverage.append(ObligationAdmissionCoverage(obligation.obligation_id,
            "static_not_executed" if static else "blocked_runtime_evidence", (),
            tuple(row.scenario_id for row in selected), "static_satisfied" if static else "not_yet_measured"))
    measured["coverage_projection_seconds"] += perf_counter() - tick
    admission = BehavioralExecutionAdmission(plan.fingerprint,
        **{name: getattr(plan, name) for name in _LINEAGE},
        scope_admission_fingerprint=plan.admission_fingerprint,
        evidence_requirement_fingerprint=authority.evidence_requirement_fingerprint,
        repository_id=admitted_scope.repository_id,
        repository_evidence_fingerprint=admitted_scope.repository_evidence_fingerprint,
        evidence_authority=authority, capability_descriptors=capabilities,
        reflection_descriptor=descriptor, admitted_scenarios=(), blocked_scenarios=tuple(decisions),
        admitted_invocation_targets=(), admitted_observation_requests=(), admitted_reflection_requests=(),
        admitted_capability_descriptors=(), coverage=tuple(coverage),
        static_satisfied_obligations=plan.static_satisfied_obligations,
        implementation_calculations=plan.implementation_calculations, status="admission_authority_incomplete")
    tick = perf_counter()
    payload = admission.as_dict()
    _payload_gate(payload)
    if len(_json(payload).encode("utf-8")) > MAX_ADMISSION_BYTES:
        _fail("admission_invalid", "admission byte bound")
    measured["admission_fingerprinting_seconds"] += perf_counter() - tick
    return admission


def build_behavioral_execution_admission(execution_plan, *, specification, compile_receipt,
        materialized, candidate, admitted_scope, reflection_descriptor=_LOCAL_REFLECTION,
        timings=None, **fresh_inputs):
    """Classify every canonical scenario without executing or granting writes."""
    measured = {} if timings is None else timings
    measured.update({key: 0.0 for key in TIMING_FIELDS})
    began = perf_counter()
    try:
        return _run(execution_plan, specification, compile_receipt, materialized, candidate,
            admitted_scope, reflection_descriptor, fresh_inputs, measured)
    except BehavioralExecutionAdmissionError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("admission_invalid", type(exc).__name__)
    finally:
        measured["total_seconds"] = perf_counter() - began


def validate_behavioral_execution_admission(admission, *, execution_plan, specification,
        compile_receipt, materialized, candidate, admitted_scope,
        reflection_descriptor=_LOCAL_REFLECTION, timings=None, **fresh_inputs):
    """Reconstruct every parent, capability, request, fixture and decision."""
    try:
        payload = admission.as_dict() if type(admission) is BehavioralExecutionAdmission else admission
        if type(payload) is not dict:
            _fail("admission_invalid", "closed admission payload required")
        _payload_gate(payload)
        if (set(payload) != {descriptor.name for descriptor in fields(BehavioralExecutionAdmission)}
                | {"admission_fingerprint"} or len(_json(payload).encode("utf-8")) > MAX_ADMISSION_BYTES):
            _fail("admission_invalid", "closed bounded admission schema required")
        rebuilt = build_behavioral_execution_admission(execution_plan, specification=specification,
            compile_receipt=compile_receipt, materialized=materialized, candidate=candidate,
            admitted_scope=admitted_scope, reflection_descriptor=reflection_descriptor,
            timings=timings, **fresh_inputs)
        expected = rebuilt.as_dict()
        if _json(payload) != _json(expected):
            lineage = (*_LINEAGE, "execution_plan_fingerprint", "scope_admission_fingerprint",
                "evidence_requirement_fingerprint", "repository_id", "repository_evidence_fingerprint",
                "evidence_authority", "reflection_descriptor", "capability_descriptors")
            _fail("admission_stale" if any(_json(payload[name]) != _json(expected[name]) for name in lineage)
                else "admission_scope_mismatch", "exact reconstructed admission differs")
        return rebuilt
    except BehavioralExecutionAdmissionError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("admission_invalid", type(exc).__name__)
