"""PREFLIGHT.RUNTIME.1: exact diagnostic policy authority, never an executor.

Evidence needs, compile permission, reflection capabilities and human Apply
approval do not issue runtime permission. The frozen owners have no operational
source of this authority. A separate, explicitly synthetic process-local seam
proves the contract; its serialized projection is never a human approval.

Only supplied exact parent objects and buffers are consumed. Effect boundaries
are policy requirements for a future fixed adapter, not enforced isolation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from hashlib import sha256
import hmac
import json
import math
import secrets
from time import perf_counter

from core import behavioral_execution_admission as admission_owner
from core import behavioral_evidence_execution_plan as planner
from core import read_only_reflection as reflection
from core.structural_patch_author import StructuralPatchCandidate
from core.structural_scope_admission import AdmittedStructuralAuthoringScope

PHASE_ID = "PREFLIGHT.RUNTIME.1"
SCHEMA_VERSION = "preflight_runtime_1_v1"
SOURCE_SCHEMA_VERSION = "preflight_runtime_1_synthetic_source_v1"
PURPOSE = "diagnostic_behavioral_evidence_acquisition"
AUTHORIZATION_SOURCE_KINDS = frozenset({"explicit_typed_task_runtime_authority",
    "explicit_human_runtime_authorization", "frozen_policy_pre_authorization"})
# Category names describe future owner contracts; none is currently integrated.
OPERATIONAL_AUTHORIZATION_SOURCE_KINDS = frozenset()
FIRST_REMAINING_BLOCKER = "diagnostic_execution_authority_missing"
TIMING_FIELDS = ("parent_reconstruction_seconds", "authority_source_validation_seconds",
    "scope_projection_seconds", "scenario_binding_seconds", "effect_boundary_validation_seconds",
    "authorization_fingerprinting_seconds", "total_seconds")
MAX_AUTHORIZATION_BYTES = 512_000
_LOCAL_REFLECTION = object()
_SOURCE_SECRET = secrets.token_bytes(32)
_LINEAGE = ("task_fingerprint", "effective_design_fingerprint", "implementation_plan_fingerprint",
    "scope_admission_fingerprint", "candidate_fingerprint", "materialization_fingerprint",
    "compile_receipt_fingerprint", "behavioral_spec_fingerprint", "execution_plan_fingerprint",
    "behavioral_admission_fingerprint", "evidence_requirement_fingerprint", "repository_id",
    "repository_evidence_fingerprint")
_FALSE_AUTHORITIES = planner.AUTHORITY_KEYS | frozenset({"repository_write_authority",
    "product_write_authority", "reflection_write_authority", "private_method_invocation_authority",
    "field_enumeration_authority", "arbitrary_member_discovery_authority", "network_authorized",
    "network_authority", "arbitrary_shell_authority", "arbitrary_filesystem_effects_authority",
    "arbitrary_environment_inspection_authority", "product_state_persistence_authority",
    "filesystem_persistence_authority", "source_write_authority", "product_mutation_authority",
    "mutation_authority", "mutation", "enumeration", "method_invocation",
    "real_human_approval", "real_session_consumed", "operational_source", "enforcement_available",
    "candidate_revision_authority", "execution_completed", "execution_ready",
    "runtime_executor_available", "console_capability_available", "behavior_validated",
    "correctness_proven", "repository_write", "product_write", "reflection_write",
    "test_write", "apply", "write", "network", "console_authority"})
_FORBIDDEN = planner.FORBIDDEN_PAYLOAD_KEYS | frozenset({"argv", "shell", "command_string",
    "java", "javac", "powershell", "PowerShell", "bash", "cmd.exe", "executor_token",
    "runtime_object", "adapter_receipt", "getDeclaredFields", "field_set",
    "shell_command", "java_command", "javac_command", "command", "commands"})
_ZERO_EFFECTS = frozenset({"java_execution_count", "reflection_execution_count", "console_open_count",
    "javac_calls", "command_execution_count", "model_calls", "author_calls", "repository_traversals",
    "source_mutation", "diagnostic_harness_generation_count", "test_generation_count"})
_REQUIRED_PROHIBITIONS = frozenset({"repository_source_writes_forbidden", "product_state_persistence_forbidden",
    "network_use_forbidden", "process_spawning_beyond_fixed_runtime_adapter_forbidden",
    "arbitrary_filesystem_effects_forbidden", "arbitrary_environment_inspection_forbidden",
    "arbitrary_shell_forbidden", "reflection_writes_forbidden", "private_method_invocation_forbidden",
    "field_enumeration_forbidden", "console_authorization_forbidden"})


class RuntimeDiagnosticAuthorizationError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise RuntimeDiagnosticAuthorizationError(code, reason)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _immutable(value):
    try:
        planner._immutable(value)
    except planner.BehavioralExecutionPlanError:
        _fail("authorization_invalid", "bounded recursively immutable evidence required")


def _rows(value, kind):
    if type(value) is not tuple or len(value) > planner.MAX_ITEMS or any(type(x) is not kind for x in value):
        _fail("authorization_invalid", "bounded closed typed tuple required")


def _payload_gate(value, depth=0):
    if depth > 32:
        _fail("authorization_invalid", "nesting bound")
    if type(value) is dict:
        if len(value) > 128:
            _fail("authorization_invalid", "record bound")
        for key, item in value.items():
            if type(key) is not str:
                _fail("authorization_invalid", "closed string keys required")
            if key in _FALSE_AUTHORITIES and item is not False:
                _fail("authorization_authority_escalation", key)
            if key in _ZERO_EFFECTS and (type(item) is not int or item != 0):
                _fail("authorization_authority_escalation", key)
            if key in _REQUIRED_PROHIBITIONS and item is not True:
                _fail("authorization_authority_escalation", key)
            if key in {"authorized_diagnostic_capability_classes", "diagnostic_capability_classes"}:
                if type(item) not in {tuple, list}:
                    _fail("authorization_invalid", "closed capability tuple required")
                if any(type(c) is not str or c not in planner.CAPABILITIES
                        or c == "deterministic_console_input" for c in item):
                    _fail("authorization_authority_escalation", "no console or foreign capability grant")
            if key in _FORBIDDEN:
                _fail("authorization_invalid", "no executable payload or command surface")
            if key == "authority" and item != "bounded_runtime_diagnostic_only":
                _fail("authorization_authority_escalation", key)
            if key == "purpose" and item != PURPOSE and depth < 2:
                _fail("authorization_scope_mismatch", "exact diagnostic evidence purpose required")
            _payload_gate(item, depth + 1)
    elif type(value) in {tuple, list}:
        if len(value) > planner.MAX_ITEMS:
            _fail("authorization_invalid", "collection bound")
        for item in value:
            _payload_gate(item, depth + 1)
    elif value is not None and (type(value) not in {str, bool, int, float}
            or (type(value) is float and not math.isfinite(value))
            or (type(value) is str and len(value) > 4096)):
        _fail("authorization_invalid", "bounded scalar required")


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticEffectBoundary:
    """Mandatory future enforcement; each prohibited effect remains unpermitted."""
    repository_source_writes_forbidden: bool = field(default=True, init=False)
    product_state_persistence_forbidden: bool = field(default=True, init=False)
    network_use_forbidden: bool = field(default=True, init=False)
    process_spawning_beyond_fixed_runtime_adapter_forbidden: bool = field(default=True, init=False)
    arbitrary_filesystem_effects_forbidden: bool = field(default=True, init=False)
    arbitrary_environment_inspection_forbidden: bool = field(default=True, init=False)
    arbitrary_shell_forbidden: bool = field(default=True, init=False)
    reflection_writes_forbidden: bool = field(default=True, init=False)
    private_method_invocation_forbidden: bool = field(default=True, init=False)
    field_enumeration_forbidden: bool = field(default=True, init=False)
    console_authorization_forbidden: bool = field(default=True, init=False)
    diagnostic_harness_generation_authorized: bool = field(default=False, init=False)
    enforcement_available: bool = field(default=False, init=False)
    enforcement_status: str = field(default="runtime_executor_capability_missing", init=False)
    future_adapter_boundary: str = field(default="fixed_bounded_diagnostic_runtime_adapter_only", init=False)


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticLineage:
    task_fingerprint: str
    effective_design_fingerprint: str
    implementation_plan_fingerprint: str
    scope_admission_fingerprint: str
    candidate_fingerprint: str
    materialization_fingerprint: str
    compile_receipt_fingerprint: str
    behavioral_spec_fingerprint: str
    execution_plan_fingerprint: str
    behavioral_admission_fingerprint: str
    evidence_requirement_fingerprint: str
    repository_id: str
    repository_evidence_fingerprint: str

    def __post_init__(self):
        _immutable(self)


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticScope:
    """Complete scenario contracts bind setup, literal fixtures and observations."""
    scenario_ids: tuple[str, ...]
    scenarios: tuple[planner.DiagnosticScenario, ...]
    invocation_targets: tuple[planner.ExactMemberBinding, ...]
    observation_targets: tuple[planner.PlannedObservation, ...]
    reflection_requests: tuple[reflection.ReadOnlyReflectionRequest, ...]
    diagnostic_capability_classes: tuple[str, ...]
    capability_descriptor_fingerprints: tuple[str, ...]

    def __post_init__(self):
        _immutable(self)
        for name, kind in (("scenario_ids", str), ("scenarios", planner.DiagnosticScenario),
                ("invocation_targets", planner.ExactMemberBinding),
                ("observation_targets", planner.PlannedObservation),
                ("reflection_requests", reflection.ReadOnlyReflectionRequest),
                ("diagnostic_capability_classes", str), ("capability_descriptor_fingerprints", str)):
            _rows(getattr(self, name), kind)
        if self.scenario_ids != tuple(s.scenario_id for s in self.scenarios):
            _fail("authorization_scope_mismatch", "complete exact scenarios required")
        if any(c not in planner.CAPABILITIES or c == "deterministic_console_input"
                for c in self.diagnostic_capability_classes):
            _fail("authorization_authority_escalation", "no console or unbound capability grant")


@dataclass(frozen=True, slots=True)
class SyntheticRuntimeAuthorizationSource:
    """Fixture-only attestation, never a real task/human/policy lifecycle record.

    The private signature authenticates issuance by this synthetic seam in the
    current process. as_dict() is report-only and cannot reconstitute authority.
    """
    source_kind: str
    fixture_id: str
    lineage: RuntimeDiagnosticLineage
    scope: RuntimeDiagnosticScope
    effect_boundaries: RuntimeDiagnosticEffectBoundary
    _signature: str = field(default="", repr=False, compare=False)
    schema_version: str = field(default=SOURCE_SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    purpose: str = field(default=PURPOSE, init=False)
    synthetic: bool = field(default=True, init=False)
    provenance: str = field(default="process_local_trusted_synthetic_fixture", init=False)
    real_human_approval: bool = field(default=False, init=False)
    real_session_consumed: bool = field(default=False, init=False)
    operational_source: bool = field(default=False, init=False)
    freshness_semantics: str = field(default="exact_structural_lineage_and_source", init=False)

    def __post_init__(self):
        _immutable(self)
        if (self.source_kind not in AUTHORIZATION_SOURCE_KINDS or type(self.fixture_id) is not str
                or not self.fixture_id.startswith("synthetic") or len(self.fixture_id) > 160
                or type(self.lineage) is not RuntimeDiagnosticLineage
                or type(self.scope) is not RuntimeDiagnosticScope
                or type(self.effect_boundaries) is not RuntimeDiagnosticEffectBoundary):
            _fail("authorization_source_invalid", "closed unmistakably synthetic source required")

    def as_dict(self):
        payload = asdict(self)
        payload.pop("_signature")
        return {**json.loads(_json(payload)), "authorization_source_fingerprint": _hash(payload)}

    @property
    def fingerprint(self):
        return self.as_dict()["authorization_source_fingerprint"]

    def to_json(self):
        return _json(self.as_dict())


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticScenarioAuthorization:
    scenario_id: str
    scenario: planner.DiagnosticScenario
    status: str
    reasons: tuple[str, ...]
    diagnostic_runtime_policy_authorized: bool
    capability_available: bool
    runtime_executor_available: bool = field(default=False, init=False)
    execution_ready: bool = field(default=False, init=False)
    execution_completed: bool = field(default=False, init=False)
    console_authorized: bool = field(default=False, init=False)

    def __post_init__(self):
        _immutable(self)
        _rows(self.reasons, str)
        if (type(self.scenario) is not planner.DiagnosticScenario or self.scenario_id != self.scenario.scenario_id
                or self.status not in {"blocked_authority", "blocked_missing_capability", "blocked_semantic_gap",
                    "authorized_but_executor_unavailable"}
                or type(self.diagnostic_runtime_policy_authorized) is not bool
                or type(self.capability_available) is not bool):
            _fail("authorization_invalid", "closed exact scenario classification required")

    @property
    def policy_authorized(self):
        return self.diagnostic_runtime_policy_authorized


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticAuthorization:
    task_fingerprint: str
    effective_design_fingerprint: str
    implementation_plan_fingerprint: str
    scope_admission_fingerprint: str
    candidate_fingerprint: str
    materialization_fingerprint: str
    compile_receipt_fingerprint: str
    behavioral_spec_fingerprint: str
    execution_plan_fingerprint: str
    behavioral_admission_fingerprint: str
    evidence_requirement_fingerprint: str
    repository_id: str
    repository_evidence_fingerprint: str
    authorization_source_kind: str
    authorization_source_fingerprint: str
    authorization_source_synthetic: bool
    authorization_source_fixture_id: str
    authorized_scenario_ids: tuple[str, ...]
    authorized_scenarios: tuple[planner.DiagnosticScenario, ...]
    authorized_invocation_targets: tuple[planner.ExactMemberBinding, ...]
    authorized_observation_targets: tuple[planner.PlannedObservation, ...]
    authorized_reflection_requests: tuple[reflection.ReadOnlyReflectionRequest, ...]
    authorized_diagnostic_capability_classes: tuple[str, ...]
    capability_descriptor_fingerprints: tuple[str, ...]
    scenarios: tuple[RuntimeDiagnosticScenarioAuthorization, ...]
    effect_boundaries: RuntimeDiagnosticEffectBoundary
    diagnostic_runtime_policy_authorized: bool
    reflection_capability_available: bool
    status: str
    first_remaining_blocker: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    purpose: str = field(default=PURPOSE, init=False)
    authority: str = field(default="bounded_runtime_diagnostic_only", init=False)
    freshness_semantics: str = field(default="exact_structural_lineage_and_source", init=False)
    runtime_executor_available: bool = field(default=False, init=False)
    runtime_executor_status: str = field(default="runtime_executor_capability_missing", init=False)
    console_capability_available: bool = field(default=False, init=False)
    console_authorized: bool = field(default=False, init=False)
    execution_ready: bool = field(default=False, init=False)
    execution_completed: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    java_execution_authorized: bool = field(default=False, init=False)
    reflection_authorized: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    product_write_authority: bool = field(default=False, init=False)
    write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    test_write_authority: bool = field(default=False, init=False)
    reflection_write_authority: bool = field(default=False, init=False)
    private_method_invocation_authority: bool = field(default=False, init=False)
    field_enumeration_authority: bool = field(default=False, init=False)
    arbitrary_member_discovery_authority: bool = field(default=False, init=False)
    network_authorized: bool = field(default=False, init=False)
    arbitrary_shell_authority: bool = field(default=False, init=False)
    arbitrary_filesystem_effects_authority: bool = field(default=False, init=False)
    arbitrary_environment_inspection_authority: bool = field(default=False, init=False)
    product_state_persistence_authority: bool = field(default=False, init=False)
    diagnostic_harness_generation_authorized: bool = field(default=False, init=False)
    real_human_approval: bool = field(default=False, init=False)
    real_session_consumed: bool = field(default=False, init=False)
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

    def __post_init__(self):
        _immutable(self)
        for name, kind in (("authorized_scenario_ids", str), ("authorized_scenarios", planner.DiagnosticScenario),
                ("authorized_invocation_targets", planner.ExactMemberBinding),
                ("authorized_observation_targets", planner.PlannedObservation),
                ("authorized_reflection_requests", reflection.ReadOnlyReflectionRequest),
                ("authorized_diagnostic_capability_classes", str), ("capability_descriptor_fingerprints", str),
                ("scenarios", RuntimeDiagnosticScenarioAuthorization)):
            _rows(getattr(self, name), kind)
        if (type(self.effect_boundaries) is not RuntimeDiagnosticEffectBoundary
                or type(self.diagnostic_runtime_policy_authorized) is not bool
                or type(self.reflection_capability_available) is not bool
                or type(self.authorization_source_synthetic) is not bool
                or self.authorization_source_kind not in AUTHORIZATION_SOURCE_KINDS | {"none"}
                or self.status not in {"diagnostic_execution_authority_missing",
                    "authorized_but_executor_unavailable", "blocked_missing_capability", "blocked_semantic_gap"}):
            _fail("authorization_invalid", "closed policy and capability matrix required")

    @property
    def policy_authorized(self):
        return self.diagnostic_runtime_policy_authorized

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    @property
    def authorization_fingerprint(self):
        return self.fingerprint

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "authorization_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _parents(execution_plan, specification, compile_receipt, materialized, candidate,
        admitted_scope, behavioral_admission, reflection_descriptor, inputs, measured):
    if "repository_root" in inputs:
        _fail("authorization_invalid", "only supplied exact lineage buffers are consumed")
    expected_types = ((execution_plan, planner.BehavioralEvidenceExecutionPlan),
        (specification, planner.oracle.BehavioralValidationSpecification),
        (compile_receipt, planner.oracle.compiler.StructuralCompileValidationReceipt),
        (materialized, planner.oracle.compiler.materializer.MaterializedStructuralCandidate),
        (candidate, StructuralPatchCandidate), (admitted_scope, AdmittedStructuralAuthoringScope))
    if any(type(value) is not kind for value, kind in expected_types):
        _fail("authorization_invalid", "exact typed frozen parents required")
    tick = perf_counter()
    descriptor = (reflection.get_read_only_reflection_capability_descriptor()
        if reflection_descriptor is _LOCAL_REFLECTION else reflection_descriptor)
    try:
        plan = planner.validate_behavioral_evidence_execution_plan(execution_plan,
            specification=specification, compile_receipt=compile_receipt, materialized=materialized,
            candidate=candidate, admitted_scope=admitted_scope, **inputs)
        # Frozen admission reconstructs capability descriptors and exact REFLECT.1
        # requests; its negative authority decision remains historically intact.
        arguments = dict(execution_plan=plan, specification=specification,
            compile_receipt=compile_receipt, materialized=materialized, candidate=candidate,
            admitted_scope=admitted_scope, reflection_descriptor=descriptor, **inputs)
        if behavioral_admission is None:
            admission = admission_owner.build_behavioral_execution_admission(**arguments)
        else:
            if type(behavioral_admission) is not admission_owner.BehavioralExecutionAdmission:
                _fail("authorization_invalid", "exact typed frozen admission required")
            admission = admission_owner.validate_behavioral_execution_admission(behavioral_admission, **arguments)
    except (planner.BehavioralExecutionPlanError, admission_owner.BehavioralExecutionAdmissionError) as exc:
        _fail("authorization_authority_escalation" if "authority_escalation" in exc.code
            else "authorization_invalid" if reflection_descriptor is not _LOCAL_REFLECTION
                and exc.code == "admission_invalid" else "authorization_stale", exc.code + ": " + exc.reason)
    finally:
        measured["parent_reconstruction_seconds"] += perf_counter() - tick
    lineage = RuntimeDiagnosticLineage(**{
        name: admission.fingerprint if name == "behavioral_admission_fingerprint" else getattr(admission, name)
        for name in _LINEAGE})
    return plan, admission, lineage


def _reflection_parents(requests, plan, admission, parents, measured):
    """Validate supplied REFLECT parents; never invent a requested observation."""
    _rows(requests, reflection.ReadOnlyReflectionRequest)
    tick = perf_counter()
    try:
        canonical = {(r.scenario_id, r.observation_id): r for row in admission.scenarios
            for r in row.reflection_requests}
        supplied_ids = set()
        for request in requests:
            identity = (request.scenario_id, request.observation_id)
            if identity in supplied_ids:
                _fail("authorization_scope_mismatch", "duplicate exact reflection parent")
            supplied_ids.add(identity)
            try:
                checked = reflection.validate_read_only_reflection_request(request,
                    execution_plan=plan, **parents)
            except reflection.ReadOnlyReflectionError as exc:
                _fail("authorization_authority_escalation" if "authority_escalation" in exc.code
                    else "authorization_stale", exc.code + ": " + exc.reason)
            if identity in canonical and canonical[identity] != checked:
                _fail("authorization_scope_mismatch", "conflicting exact reflection parent")
            canonical[identity] = checked
        return canonical
    finally:
        measured["parent_reconstruction_seconds"] += perf_counter() - tick


def _project_scope(plan, admission, scenario_ids, reflection_requests):
    _rows(scenario_ids, str)
    if not scenario_ids or len(set(scenario_ids)) != len(scenario_ids):
        _fail("authorization_scope_mismatch", "nonempty exact unique scenario IDs required")
    by_id = {s.scenario_id: s for s in plan.scenarios}
    if any(s not in by_id or "*" in s for s in scenario_ids):
        _fail("authorization_scope_mismatch", "scenario outside exact execution plan")
    selected = tuple(by_id[s] for s in sorted(scenario_ids))
    calls = tuple(target for scenario in selected
        for target in ((scenario.constructor,) if scenario.constructor else ()) + tuple(
            invocation.target for invocation in (*scenario.setup_invocations,
                *((scenario.invocation,) if scenario.invocation else ()))))
    # Exact state query methods are runtime invocations as well as observations.
    queries = tuple(o.target for s in selected for o in s.observations
        if o.mechanism == "existing_exact_state_query" and o.target is not None)
    invocations = admission_owner._unique_targets((*calls, *queries))
    if any(t.visibility == "private" or t.kind not in {"constructor", "method"} for t in invocations):
        _fail("authorization_authority_escalation", "no private method invocation")
    observations = tuple(o for s in selected for o in s.observations)
    requests = []
    for scenario in selected:
        for observation in scenario.observations:
            if observation.mechanism != "read_only_reflection":
                continue
            request = reflection_requests.get((scenario.scenario_id, observation.observation_id))
            if request is None:
                _fail("authorization_scope_mismatch", "complete scenario requires an existing exact REFLECT parent")
            requests.append(request)
    if any(o.mechanism == "read_only_reflection" and o.reflection_operation != "read_exact_bound_field"
            for o in observations):
        _fail("authorization_authority_escalation", "only exact bound field reads")
    # Console attachment needs stay in the complete scenario, but this phase
    # grants no console authority and cannot make that capability available.
    capabilities = tuple(sorted({c for s in selected for c in s.required_capabilities
        if c != "deterministic_console_input"}))
    descriptor_map = {c.capability: c for c in admission.capability_descriptors}
    fingerprints = tuple(descriptor_map[c].fingerprint for c in sorted({
        c for s in selected for c in s.required_capabilities}))
    return RuntimeDiagnosticScope(tuple(s.scenario_id for s in selected), selected, invocations,
        observations, tuple(requests), capabilities, fingerprints)


def _signature(source):
    return hmac.new(_SOURCE_SECRET, source.to_json().encode("utf-8"), sha256).hexdigest()


def issue_synthetic_runtime_authorization_source(execution_plan, *, specification, compile_receipt,
        materialized, candidate, admitted_scope, scenario_ids, fixture_id,
        source_kind="explicit_human_runtime_authorization", behavioral_admission=None,
        reflection_descriptor=_LOCAL_REFLECTION, reflection_requests=(), **fresh_inputs):
    """Issue fixture provenance only; never inspect, consume or approve a session.

    Production authority issuers/UI integration remain future work. Callers
    must deliberately choose an unmistakable synthetic fixture identity.
    """
    measured = {key: 0.0 for key in TIMING_FIELDS}
    try:
        plan, admission, lineage = _parents(execution_plan, specification, compile_receipt,
            materialized, candidate, admitted_scope, behavioral_admission,
            reflection_descriptor, fresh_inputs, measured)
        parents = dict(specification=specification, compile_receipt=compile_receipt,
            materialized=materialized, candidate=candidate, admitted_scope=admitted_scope, **fresh_inputs)
        requests = _reflection_parents(reflection_requests, plan, admission, parents, measured)
        source = SyntheticRuntimeAuthorizationSource(source_kind, fixture_id, lineage,
            _project_scope(plan, admission, scenario_ids, requests), RuntimeDiagnosticEffectBoundary())
        _payload_gate(source.as_dict())
        if len(source.to_json().encode("utf-8")) > MAX_AUTHORIZATION_BYTES:
            _fail("authorization_source_invalid", "synthetic source byte bound")
        # The public constructor produces no attestation. Only the explicit
        # synthetic seam signs an exact reconstructed fixture record.
        object.__setattr__(source, "_signature", _signature(source))
        return source
    except RuntimeDiagnosticAuthorizationError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("authorization_source_invalid", type(exc).__name__)


def _validate_source(source, plan, admission, lineage, reflection_requests, measured):
    if source is None:
        return None
    tick = perf_counter()
    try:
        if type(source) is not SyntheticRuntimeAuthorizationSource:
            _fail("authorization_source_invalid", "caller-authored approval JSON is not trusted provenance")
        source.__post_init__()
        _payload_gate(source.as_dict())
        if len(source.to_json().encode("utf-8")) > MAX_AUTHORIZATION_BYTES:
            _fail("authorization_source_invalid", "synthetic source byte bound")
        if (type(source._signature) is not str or not source._signature
                or not hmac.compare_digest(source._signature, _signature(source))):
            _fail("authorization_source_invalid", "process-local synthetic issuer attestation missing or altered")
        if asdict(source.lineage) != asdict(lineage):
            _fail("authorization_stale", "authority source bound to different exact lineage")
        if (source.schema_version != SOURCE_SCHEMA_VERSION or source.phase_id != PHASE_ID
                or source.purpose != PURPOSE or source.synthetic is not True
                or source.provenance != "process_local_trusted_synthetic_fixture"
                or source.real_human_approval is not False or source.real_session_consumed is not False
                or source.operational_source is not False
                or source.freshness_semantics != "exact_structural_lineage_and_source"):
            _fail("authorization_source_invalid", "fixture provenance cannot become real human authority")
    finally:
        measured["authority_source_validation_seconds"] += perf_counter() - tick
    tick = perf_counter()
    try:
        expected_scope = _project_scope(plan, admission, source.scope.scenario_ids, reflection_requests)
        if asdict(source.scope) != asdict(expected_scope):
            _fail("authorization_scope_mismatch", "exact atomic scenario projection differs")
        if asdict(source.effect_boundaries) != asdict(RuntimeDiagnosticEffectBoundary()):
            _fail("authorization_authority_escalation", "future effect prohibitions are fixed")
    finally:
        measured["scope_projection_seconds"] += perf_counter() - tick
    return expected_scope


def _run(execution_plan, specification, compile_receipt, materialized, candidate, admitted_scope,
        source, behavioral_admission, reflection_descriptor, reflection_requests, inputs, measured):
    plan, admission, lineage = _parents(execution_plan, specification, compile_receipt,
        materialized, candidate, admitted_scope, behavioral_admission, reflection_descriptor, inputs, measured)
    parents = dict(specification=specification, compile_receipt=compile_receipt,
        materialized=materialized, candidate=candidate, admitted_scope=admitted_scope, **inputs)
    requests = _reflection_parents(reflection_requests, plan, admission, parents, measured)
    scope = _validate_source(source, plan, admission, lineage, requests, measured)
    tick = perf_counter()
    selected = () if scope is None else scope.scenario_ids
    decisions = []
    for row in admission.scenarios:
        policy_authorized = row.scenario_id in selected
        if not row.capability_eligible:
            status, reasons = row.status, row.reasons
        elif policy_authorized:
            status, reasons = "authorized_but_executor_unavailable", ("runtime_executor_capability_missing",)
        else:
            status, reasons = "blocked_authority", ("diagnostic_execution_authority_missing",)
        decisions.append(RuntimeDiagnosticScenarioAuthorization(row.scenario_id, row.scenario, status,
            reasons, policy_authorized, row.capability_eligible))
    chosen = tuple(row for row in decisions if row.policy_authorized)
    if not chosen:
        status, blocker = "diagnostic_execution_authority_missing", FIRST_REMAINING_BLOCKER
    elif any(row.capability_available for row in chosen):
        status, blocker = "authorized_but_executor_unavailable", "runtime_executor_capability_missing"
    elif any(row.status == "blocked_semantic_gap" for row in chosen):
        status, blocker = "blocked_semantic_gap", next(row.reasons[0] for row in chosen
            if row.status == "blocked_semantic_gap")
    else:
        status, blocker = "blocked_missing_capability", chosen[0].reasons[0]
    authorization = RuntimeDiagnosticAuthorization(**asdict(lineage),
        authorization_source_kind="none" if source is None else source.source_kind,
        authorization_source_fingerprint="" if source is None else source.fingerprint,
        authorization_source_synthetic=source is not None,
        authorization_source_fixture_id="" if source is None else source.fixture_id,
        authorized_scenario_ids=selected, authorized_scenarios=() if scope is None else scope.scenarios,
        authorized_invocation_targets=() if scope is None else scope.invocation_targets,
        authorized_observation_targets=() if scope is None else scope.observation_targets,
        authorized_reflection_requests=() if scope is None else scope.reflection_requests,
        authorized_diagnostic_capability_classes=() if scope is None else scope.diagnostic_capability_classes,
        capability_descriptor_fingerprints=() if scope is None else scope.capability_descriptor_fingerprints,
        scenarios=tuple(decisions), effect_boundaries=RuntimeDiagnosticEffectBoundary(),
        diagnostic_runtime_policy_authorized=bool(chosen),
        reflection_capability_available=admission.reflection_descriptor is not None,
        status=status, first_remaining_blocker=blocker)
    measured["scenario_binding_seconds"] += perf_counter() - tick
    tick = perf_counter()
    payload = asdict(authorization)
    _payload_gate(payload)
    measured["effect_boundary_validation_seconds"] += perf_counter() - tick
    tick = perf_counter()
    payload = authorization.as_dict()
    if len(_json(payload).encode("utf-8")) > MAX_AUTHORIZATION_BYTES:
        _fail("authorization_invalid", "authorization byte bound")
    measured["authorization_fingerprinting_seconds"] += perf_counter() - tick
    return authorization


def build_runtime_diagnostic_authorization(execution_plan, *, specification, compile_receipt,
        materialized, candidate, admitted_scope, authorization_source=None, behavioral_admission=None,
        reflection_descriptor=_LOCAL_REFLECTION, reflection_requests=(), timings=None, **fresh_inputs):
    """Reconstruct exact bounded policy scope while reporting executor absence."""
    measured = {} if timings is None else timings
    measured.update({key: 0.0 for key in TIMING_FIELDS})
    began = perf_counter()
    try:
        return _run(execution_plan, specification, compile_receipt, materialized, candidate,
            admitted_scope, authorization_source, behavioral_admission, reflection_descriptor,
            reflection_requests, fresh_inputs, measured)
    except RuntimeDiagnosticAuthorizationError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("authorization_invalid", type(exc).__name__)
    finally:
        measured["total_seconds"] = perf_counter() - began


def validate_runtime_diagnostic_authorization(authorization, *, execution_plan, specification,
        compile_receipt, materialized, candidate, admitted_scope, authorization_source=None,
        behavioral_admission=None, reflection_descriptor=_LOCAL_REFLECTION, reflection_requests=(),
        timings=None, **fresh_inputs):
    """Independent pure reconstruction; hashes/JSON/UI state do not issue consent."""
    try:
        payload = authorization.as_dict() if type(authorization) is RuntimeDiagnosticAuthorization else authorization
        if type(payload) is not dict:
            _fail("authorization_invalid", "closed authorization payload required")
        _payload_gate(payload)
        if (set(payload) != {f.name for f in fields(RuntimeDiagnosticAuthorization)} | {"authorization_fingerprint"}
                or len(_json(payload).encode("utf-8")) > MAX_AUTHORIZATION_BYTES):
            _fail("authorization_invalid", "closed bounded authorization schema required")
        rebuilt = build_runtime_diagnostic_authorization(execution_plan, specification=specification,
            compile_receipt=compile_receipt, materialized=materialized, candidate=candidate,
            admitted_scope=admitted_scope, authorization_source=authorization_source,
            behavioral_admission=behavioral_admission, reflection_descriptor=reflection_descriptor,
            reflection_requests=reflection_requests, timings=timings, **fresh_inputs)
        expected = rebuilt.as_dict()
        if _json(payload) != _json(expected):
            stale = (*_LINEAGE, "authorization_source_kind", "authorization_source_fingerprint",
                "authorization_source_synthetic", "authorization_source_fixture_id")
            _fail("authorization_stale" if any(_json(payload[name]) != _json(expected[name]) for name in stale)
                else "authorization_scope_mismatch", "exact reconstructed authorization differs")
        return rebuilt
    except RuntimeDiagnosticAuthorizationError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("authorization_invalid", type(exc).__name__)
