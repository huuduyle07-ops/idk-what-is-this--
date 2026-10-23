"""One exact diagnostic field read; capability availability grants no execution.

Authorization is rebuilt from frozen EXEC.PLAN/SPEC/materialization evidence.
This module neither acquires repository files nor executes or constructs product
objects. Serialized observations need a separate receipt issued by the bounded
adapter; a payload's own fingerprint is never proof that a read happened.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from hashlib import sha256
import hmac
import json
import math
import secrets
import re
import struct
from time import perf_counter

from core import behavioral_evidence_execution_plan as planner
from core.structural_java import children, compact, get_parser, text

PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1"
SCHEMA_VERSION = "patch_candidate_behavior_reflect_1_v1"
ADAPTER_VERSION = "exact_read_only_reflection_v1"
FIRST_REMAINING_BLOCKER = "STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_NOT_IMPLEMENTED"
TIMING_FIELDS = ("request_authorization_reconstruction_seconds", "exact_target_validation_seconds",
    "adapter_reflection_read_seconds", "value_normalization_seconds",
    "observation_fingerprinting_seconds", "total_synthetic_diagnostic_overhead_seconds")
OBSERVATION_ROLES = frozenset({"ordinary_balance_before", "ordinary_balance_after",
    "savings_balance_before", "savings_balance_after"})
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_BITS = re.compile(r"[0-9a-f]{16}\Z")
_MAX_BYTES = 32_000
_AUTHORITY_KEYS = planner.AUTHORITY_KEYS | frozenset({"mutation_authority", "product_mutation_authority",
    "source_write_authority", "reflection_write_authority", "private_method_invocation_authority",
    "arbitrary_member_discovery_authority", "mutation", "enumeration", "method_invocation", "mutate"})
_FORBIDDEN_OPERATIONS = frozenset({"write_value", "set_field", "write_field", "field_set", "setDouble",
    "setInt", "reflection_write", "invoke_private_method", "call_method", "construct_object",
    "mutate_object", "set_accessible_for_arbitrary_member"})
_ENUMERATION_KEYS = frozenset({"enumerate_fields", "list_fields", "discover_private_members",
    "getDeclaredFields", "getFields", "read_field_by_pattern"})
_RECEIPT_SECRET = secrets.token_bytes(32)


class ReadOnlyReflectionError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise ReadOnlyReflectionError(code, reason)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _immutable(value):
    if value is None or type(value) in {str, bool, int}:
        if type(value) is str and len(value) > 2048:
            _fail("reflection_invalid", "bounded scalar required")
        return
    if type(value) is tuple and len(value) <= 64:
        for item in value:
            _immutable(item)
    elif is_dataclass(value) and value.__dataclass_params__.frozen:
        for descriptor in fields(value):
            _immutable(getattr(value, descriptor.name))
    else:
        _fail("reflection_invalid", "bounded immutable evidence required")


def _digest(value):
    if type(value) is not str or _HEX.fullmatch(value) is None:
        _fail("reflection_invalid", "exact SHA-256 identity required")


def _gate(value):
    if type(value) is dict:
        if len(value) > 64:
            _fail("reflection_invalid", "closed schema bound")
        for key, item in value.items():
            if type(key) is not str:
                _fail("reflection_invalid", "string schema keys required")
            if key in _AUTHORITY_KEYS and item is not False:
                _fail("reflection_authority_escalation", key)
            if key in _FORBIDDEN_OPERATIONS:
                _fail("reflection_authority_escalation", key)
            if key in _ENUMERATION_KEYS:
                _fail("reflection_invalid", "member discovery is unsupported")
            if key == "operation" and item != "read_exact_bound_field":
                _fail("reflection_authority_escalation" if item in _FORBIDDEN_OPERATIONS else
                    "reflection_invalid", "one closed read operation required")
            _gate(item)
    elif type(value) in {list, tuple}:
        if len(value) > 64:
            _fail("reflection_invalid", "collection bound")
        for item in value:
            _gate(item)
    elif value is not None and type(value) not in {str, bool, int}:
        _fail("reflection_invalid", "closed scalar schema required")


def _payload(value, kind, fingerprint_name):
    payload = value.as_dict() if type(value) is kind else value
    if type(payload) is not dict:
        _fail("reflection_invalid", "closed typed payload required")
    _gate(payload)
    if len(_json(payload).encode("utf-8")) > _MAX_BYTES:
        _fail("reflection_invalid", "payload byte bound")
    if set(payload) != {f.name for f in fields(kind)} | {fingerprint_name}:
        _fail("reflection_invalid", "closed payload schema required")
    return payload


@dataclass(frozen=True, slots=True)
class ReadOnlyReflectionCapabilityDescriptor:
    capability: str = field(default="read_only_reflection", init=False)
    operation: str = field(default="read_exact_bound_field", init=False)
    supported_value_types: tuple[str, ...] = field(default=("double",), init=False)
    availability: str = field(default="available_but_not_execution_admitted", init=False)
    adapter_version: str = field(default=ADAPTER_VERSION, init=False)
    mutation: bool = field(default=False, init=False)
    enumeration: bool = field(default=False, init=False)
    method_invocation: bool = field(default=False, init=False)
    product_mutation_authority: bool = field(default=False, init=False)
    source_write_authority: bool = field(default=False, init=False)
    reflection_write_authority: bool = field(default=False, init=False)
    private_method_invocation_authority: bool = field(default=False, init=False)
    arbitrary_member_discovery_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "capability_descriptor_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


_DESCRIPTOR = ReadOnlyReflectionCapabilityDescriptor()


def get_read_only_reflection_capability_descriptor():
    """Fixed implementation truth, with no object handles or execution grant."""
    return _DESCRIPTOR


def validate_read_only_reflection_capability_descriptor(descriptor):
    payload = _payload(descriptor, ReadOnlyReflectionCapabilityDescriptor, "capability_descriptor_fingerprint")
    if _json(payload) != _json(ReadOnlyReflectionCapabilityDescriptor().as_dict()):
        _fail("reflection_invalid", "descriptor differs from the bounded local implementation")
    return _DESCRIPTOR


@dataclass(frozen=True, slots=True)
class RuntimeClassBinding:
    path: str
    qualified_owner: str
    binary_owner: str
    declaring_binary_owner: str
    relationship: str
    source_sha256: str
    definition_sha256: str
    declared_superclass: str
    package_name: str

    @property
    def source_owner(self):
        return (self.package_name + "." if self.package_name else "") + self.qualified_owner.replace("::", ".")

    def __post_init__(self):
        _immutable(self)
        if self.relationship not in {"same_class", "exact_direct_superclass"}:
            _fail("reflection_target_mismatch", "only the validated exact owner relationship is supported")
        _digest(self.source_sha256)
        _digest(self.definition_sha256)


@dataclass(frozen=True, slots=True)
class ReadOnlyReflectionRequest:
    execution_plan_fingerprint: str
    behavioral_spec_fingerprint: str
    materialization_fingerprint: str
    scenario_id: str
    obligation_ids: tuple[str, ...]
    observation_id: str
    observation_role: str
    target: planner.ExactMemberBinding
    runtime_binding: RuntimeClassBinding
    capability_descriptor_fingerprint: str
    operation: str = field(default="read_exact_bound_field", init=False)
    instance_field: bool = field(default=True, init=False)
    mutation_authority: bool = field(default=False, init=False)
    product_mutation_authority: bool = field(default=False, init=False)
    source_write_authority: bool = field(default=False, init=False)
    reflection_write_authority: bool = field(default=False, init=False)
    private_method_invocation_authority: bool = field(default=False, init=False)
    arbitrary_member_discovery_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self):
        _immutable(self)
        if (type(self.target) is not planner.ExactMemberBinding or type(self.runtime_binding) is not RuntimeClassBinding
                or self.target.kind != "field" or self.target.declared_type != "double"
                or self.observation_role not in OBSERVATION_ROLES or type(self.obligation_ids) is not tuple
                or any(type(x) is not str for x in self.obligation_ids)):
            _fail("reflection_invalid", "exact typed numeric field and closed observation role required")
        for value in (self.execution_plan_fingerprint, self.behavioral_spec_fingerprint,
                self.materialization_fingerprint, self.capability_descriptor_fingerprint):
            _digest(value)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "request_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _sources(materialized, inputs):
    sources = planner.oracle.compiler.materializer._sources(inputs)
    sources.update({f.path: f.after_bytes for f in materialized.virtual_files})
    return sources


def _class(path, qualified_owner, raw):
    root = get_parser("java").parse(raw).root_node
    if root.has_error:
        _fail("reflection_target_stale", "materialized Java syntax is incomplete")
    package = next((compact(children(n)[0], raw) for n in children(root) if n.type == "package_declaration"), "")
    matches = []
    def collect(node, owner=""):
        if node.type == "class_declaration":
            name = text(node.child_by_field_name("name"), raw)
            owner = (owner + "::" if owner else "") + name
            if owner == qualified_owner:
                matches.append(node)
            for child in children(node.child_by_field_name("body")):
                if child.type == "class_declaration":
                    collect(child, owner)
        else:
            for child in children(node):
                collect(child, owner)
    collect(root)
    if len(matches) != 1:
        _fail("reflection_target_stale", "exact declaring/runtime class is missing or ambiguous")
    return matches[0], package, root


def _lexical_classes(root, raw):
    """Class identity metadata in the selected source, never runtime discovery."""
    result = set()
    def collect(node, owner=""):
        if node.type == "class_declaration":
            name = text(node.child_by_field_name("name"), raw)
            owner = (owner + "::" if owner else "") + name
            result.add(owner)
            for child in children(node.child_by_field_name("body")):
                if child.type == "class_declaration":
                    collect(child, owner)
        else:
            for child in children(node):
                collect(child, owner)
    collect(root)
    return result


def _target_and_runtime(observation, scenario, materialized, inputs):
    target = observation.target
    if (type(target) is not planner.ExactMemberBinding or target.kind != "field"
            or (target.owner, target.name) not in {("BankAccount", "balance"), ("SavingAccount", "savingBalance")}
            or target.declared_type != "double" or target.parameters or target.visibility != "private"):
        _fail("reflection_target_mismatch", "V1 accepts only the two exact planned private double balances")
    sources = _sources(materialized, inputs)
    raw = sources.get(target.path)
    if raw is None or sha256(raw).hexdigest() != target.source_sha256:
        _fail("reflection_target_stale", "exact materialized source fingerprint differs")
    declaring, package, _ = _class(target.path, target.qualified_owner, raw)
    if package != target.package_name:
        _fail("reflection_target_stale", "exact package binding differs")
    declarations = []
    for node in children(declaring.child_by_field_name("body")):
        if node.type == "field_declaration":
            for declarator in children(node):
                if declarator.type == "variable_declarator" and text(declarator.child_by_field_name("name"), raw) == target.name:
                    declarations.append((node, declarator))
    if len(declarations) != 1:
        _fail("reflection_target_stale", "exact field declaration is missing or ambiguous")
    node, declarator = declarations[0]
    modifiers = next((n for n in children(node) if n.type == "modifiers"), None)
    tokens = tuple(text(n, raw) for n in modifiers.children) if modifiers else ()
    if ("static" in tokens or compact(node.child_by_field_name("type"), raw) != "double"
            or compact(declarator.child_by_field_name("dimensions"), raw)):
        _fail("reflection_target_mismatch", "exact primitive instance-field semantics required")
    if sha256(raw[node.start_byte:node.end_byte]).hexdigest() != target.definition_sha256:
        _fail("reflection_target_stale", "exact member fingerprint differs")
    constructor = scenario.constructor
    if type(constructor) is not planner.ExactMemberBinding or constructor.kind != "constructor":
        _fail("reflection_target_mismatch", "exact planned runtime owner is unavailable")
    runtime_raw = sources.get(constructor.path)
    if runtime_raw is None or sha256(runtime_raw).hexdigest() != constructor.source_sha256:
        _fail("reflection_target_stale", "runtime class source differs")
    runtime, runtime_package, runtime_root = _class(constructor.path, constructor.qualified_owner, runtime_raw)
    if runtime_package != constructor.package_name:
        _fail("reflection_target_stale", "runtime class package differs")
    superclass_node = runtime.child_by_field_name("superclass")
    super_name = compact(superclass_node, runtime_raw)
    super_name = super_name.removeprefix("extends")
    relation = "same_class" if constructor.binary_owner == target.binary_owner else "exact_direct_superclass"
    if relation == "same_class":
        if (constructor.path, constructor.qualified_owner) != (target.path, target.qualified_owner):
            _fail("reflection_target_mismatch", "runtime/declaration owner identity differs")
    else:
        # Resolve the already-selected declaration, without searching a runtime
        # superclass chain or guessing from matching class names.
        qualified_java = (target.package_name + "." if target.package_name else "") + target.qualified_owner.replace("::", ".")
        lexical = target.qualified_owner.replace("::", ".")
        allowed_spellings = {qualified_java}
        if runtime_package == target.package_name:
            allowed_spellings.add(lexical)
            if "::" not in target.qualified_owner or constructor.qualified_owner.startswith(target.qualified_owner + "::"):
                allowed_spellings.add(target.owner)
        imports = [compact(n, runtime_raw) for n in children(runtime_root) if n.type == "import_declaration"]
        for item in imports:
            imported = item.removeprefix("import").removeprefix("static").removesuffix(";")
            if imported.endswith("." + target.owner):
                if imported == qualified_java:
                    allowed_spellings.add(target.owner)
                else:
                    allowed_spellings.discard(target.owner)
        if super_name == target.owner:
            # A same-named nested declaration in an enclosing lexical scope
            # outranks a top-level same-package/import binding in Java. Resolve
            # that exact scope first, rather than aliasing it to this target.
            lexical_classes = _lexical_classes(runtime_root, runtime_raw)
            parts = constructor.qualified_owner.split("::")
            visible = next(("::".join(parts[:i]) + "::" + super_name
                for i in range(len(parts), 0, -1)
                if "::".join(parts[:i]) + "::" + super_name in lexical_classes), None)
            if visible is not None:
                if visible != target.qualified_owner:
                    _fail("reflection_target_mismatch", "a distinct lexical superclass declaration shadows the target")
                allowed_spellings.add(target.owner)
            elif any(part == target.owner for part in parts[:-1]):
                nearest = "::".join(parts[:max(i for i, part in enumerate(parts[:-1], 1) if part == target.owner)])
                if nearest != target.qualified_owner:
                    _fail("reflection_target_mismatch", "a distinct enclosing owner shadows the target")
        if super_name not in allowed_spellings:
            _fail("reflection_target_mismatch", "exact directly declared superclass relation differs")
    binding = RuntimeClassBinding(constructor.path, constructor.qualified_owner, constructor.binary_owner,
        target.binary_owner, relation, sha256(runtime_raw).hexdigest(),
        sha256(runtime_raw[runtime.start_byte:runtime.end_byte]).hexdigest(), super_name, runtime_package)
    return target, binding


def _build(execution_plan, *, scenario_id, observation_id, specification, compile_receipt,
        materialized, candidate, admitted_scope, timings, fresh_inputs):
    if type(scenario_id) is not str or type(observation_id) is not str:
        _fail("reflection_invalid", "exact typed plan selectors required")
    if "repository_root" in fresh_inputs:
        _fail("reflection_invalid", "only supplied bound evidence buffers are consumed")
    tick = perf_counter()
    try:
        plan = planner.validate_behavioral_evidence_execution_plan(execution_plan,
            specification=specification, compile_receipt=compile_receipt, materialized=materialized,
            candidate=candidate, admitted_scope=admitted_scope, **fresh_inputs)
    except planner.BehavioralExecutionPlanError as exc:
        _fail("reflection_target_stale", exc.code + ": " + exc.reason)
    finally:
        timings["request_authorization_reconstruction_seconds"] += perf_counter() - tick
    tick = perf_counter()
    try:
        scenarios = [s for s in plan.scenarios if s.scenario_id == scenario_id]
        if len(scenarios) != 1:
            _fail("reflection_target_stale", "exact execution-plan scenario differs")
        scenario = scenarios[0]
        observations = [o for o in scenario.observations if o.observation_id == observation_id]
        if len(observations) != 1:
            _fail("reflection_target_stale", "exact scenario observation differs")
        observation = observations[0]
        if observation.mechanism != "read_only_reflection" or observation.reflection_operation != "read_exact_bound_field":
            _fail("reflection_target_mismatch", "observation is not an exact reflection target")
        target, runtime = _target_and_runtime(observation, scenario, materialized, fresh_inputs)
        role = {("BankAccount", "balance"): "ordinary_balance", ("SavingAccount", "savingBalance"): "savings_balance"}[(target.owner, target.name)] + "_" + observation.moment
        # Frozen plan reconstruction has already rebound all SPEC obligations;
        # retain every exact scenario obligation, including shared observations.
        return ReadOnlyReflectionRequest(plan.fingerprint, plan.behavioral_spec_fingerprint,
            plan.materialization_fingerprint, scenario.scenario_id, scenario.obligation_ids,
            observation.observation_id, role, target, runtime, _DESCRIPTOR.fingerprint)
    finally:
        timings["exact_target_validation_seconds"] += perf_counter() - tick


def _timings(timings):
    measured = {} if timings is None else timings
    for key in TIMING_FIELDS:
        measured.setdefault(key, 0.0)
    return measured


def build_read_only_reflection_request(execution_plan, *, scenario_id, observation_id, specification,
        compile_receipt, materialized, candidate, admitted_scope, timings=None, **fresh_inputs):
    """Select exact plan IDs; caller field/class strings never supply authority."""
    measured = _timings(timings)
    began = perf_counter()
    try:
        return _build(execution_plan, scenario_id=scenario_id, observation_id=observation_id,
            specification=specification, compile_receipt=compile_receipt, materialized=materialized,
            candidate=candidate, admitted_scope=admitted_scope, timings=measured, fresh_inputs=fresh_inputs)
    except ReadOnlyReflectionError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("reflection_invalid", type(exc).__name__)
    finally:
        measured["total_synthetic_diagnostic_overhead_seconds"] += perf_counter() - began


def validate_read_only_reflection_request(request, *, execution_plan, specification, compile_receipt,
        materialized, candidate, admitted_scope, timings=None, **fresh_inputs):
    """Pure independent reconstruction of plan, oracle, target and lineage."""
    try:
        payload = _payload(request, ReadOnlyReflectionRequest, "request_fingerprint")
        rebuilt = build_read_only_reflection_request(execution_plan, scenario_id=payload["scenario_id"],
            observation_id=payload["observation_id"], specification=specification, compile_receipt=compile_receipt,
            materialized=materialized, candidate=candidate, admitted_scope=admitted_scope,
            timings=timings, **fresh_inputs)
        if _json(payload) != _json(rebuilt.as_dict()):
            _fail("reflection_target_stale", "exact request owner, member, type, source, role or plan binding differs")
        return rebuilt
    except ReadOnlyReflectionError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("reflection_invalid", type(exc).__name__)


def canonical_double_value(value):
    """Canonical finite IEEE-754 bits; no numeric coercion or object encoding."""
    if type(value) is not float:
        _fail("reflection_target_mismatch", "primitive double value required")
    if not math.isfinite(value):
        _fail("reflection_nonfinite_value", "finite double required")
    return struct.pack(">d", value).hex()


def _canonical_bits(value):
    if type(value) is not str or _BITS.fullmatch(value) is None:
        _fail("reflection_observation_invalid", "canonical 16-digit lowercase IEEE-754 bits required")
    if not math.isfinite(struct.unpack(">d", bytes.fromhex(value))[0]):
        _fail("reflection_nonfinite_value", "finite double required")
    return value


@dataclass(frozen=True, slots=True)
class AdapterDiagnosticProvenance:
    adapter_version: str
    adapter_source_sha256: str
    source_sha256: str
    runtime_identity: str
    evidence_kind: str
    product_runtime_observed: bool
    infrastructure_java_execution_count: int
    BANK_behavioral_java_execution_count: int

    def __post_init__(self):
        _immutable(self)
        _digest(self.adapter_source_sha256)
        _digest(self.source_sha256)
        if (self.adapter_version != ADAPTER_VERSION or self.evidence_kind != "synthetic_capability_fixture"
                or not self.runtime_identity):
            _fail("reflection_observation_invalid", "bounded adapter diagnostic provenance required")
        if (type(self.product_runtime_observed) is not bool or type(self.infrastructure_java_execution_count) is not int
                or type(self.BANK_behavioral_java_execution_count) is not int):
            _fail("reflection_observation_invalid", "exact diagnostic accounting types required")
        if (self.product_runtime_observed is not False or self.infrastructure_java_execution_count != 1
                or self.BANK_behavioral_java_execution_count != 0):
            _fail("reflection_authority_escalation", "this phase records synthetic infrastructure observations only")


@dataclass(frozen=True, slots=True)
class ReadOnlyReflectionObservation:
    request_fingerprint: str
    capability_descriptor_fingerprint: str
    runtime_class_identity: str
    declaring_class_identity: str
    measured_field_type: str
    canonical_value: str
    status: str
    failure_code: str
    diagnostic_provenance: AdapterDiagnosticProvenance
    mutation_authority: bool = field(default=False, init=False)
    product_mutation_authority: bool = field(default=False, init=False)
    source_write_authority: bool = field(default=False, init=False)
    reflection_write_authority: bool = field(default=False, init=False)
    private_method_invocation_authority: bool = field(default=False, init=False)
    arbitrary_member_discovery_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    operation: str = field(default="read_exact_bound_field", init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self):
        _immutable(self)
        _digest(self.request_fingerprint)
        _digest(self.capability_descriptor_fingerprint)
        if type(self.diagnostic_provenance) is not AdapterDiagnosticProvenance or self.status not in {"observed", "failed"}:
            _fail("reflection_observation_invalid", "closed diagnostic outcome required")
        if self.status == "observed":
            if self.measured_field_type != "double" or self.failure_code:
                _fail("reflection_target_mismatch", "exact successful primitive double read required")
            _canonical_bits(self.canonical_value)
        elif (self.canonical_value or self.failure_code not in {"reflection_target_mismatch", "reflection_access_denied",
                "reflection_nonfinite_value", "reflection_read_failed", "reflection_runtime_class_mismatch",
                "reflection_accessibility_restore_failed"}):
            _fail("reflection_observation_invalid", "closed failure without a measured value required")

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "observation_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


@dataclass(frozen=True, slots=True)
class AdapterReadReceipt:
    """In-process adapter evidence, deliberately not a deserializable claim."""
    observation: ReadOnlyReflectionObservation
    _signature: str = field(repr=False, compare=False)

    def __post_init__(self):
        if not _receipt_authentic(self):
            _fail("reflection_observation_untrusted", "only the bounded adapter issues read receipts")


def _receipt_signature(observation):
    return hmac.new(_RECEIPT_SECRET, observation.to_json().encode("utf-8"), sha256).hexdigest()


def _receipt_authentic(receipt):
    return (type(receipt) is AdapterReadReceipt and type(receipt.observation) is ReadOnlyReflectionObservation
        and type(receipt._signature) is str and _HEX.fullmatch(receipt._signature) is not None
        and hmac.compare_digest(receipt._signature, _receipt_signature(receipt.observation)))


def _validate_runtime_identities(request, observation):
    expected_runtime, expected_declaring = _runtime_identities(request, observation.diagnostic_provenance)
    if observation.declaring_class_identity != expected_declaring:
        _fail("reflection_target_mismatch", "exact declaration identity differs")
    if observation.runtime_class_identity != expected_runtime and not (
            observation.status == "failed" and observation.failure_code == "reflection_runtime_class_mismatch"
            and not observation.canonical_value):
        _fail("reflection_target_mismatch", "exact runtime identity differs")


def _runtime_identities(request, provenance):
    if provenance.evidence_kind == "synthetic_capability_fixture":
        # This fixed infrastructure mapping cannot turn a fixture read into
        # candidate runtime evidence. No arbitrary caller-supplied aliases.
        mapping = {"BankAccount": "ReflectionFixture", "SavingAccount": "ReflectionChild"}
        runtime_owner = request.runtime_binding.qualified_owner.split("::")[-1]
        if runtime_owner not in mapping or request.target.owner not in mapping:
            _fail("reflection_target_mismatch", "closed synthetic fixture owner required")
        if (provenance.product_runtime_observed is not False or provenance.infrastructure_java_execution_count != 1
                or provenance.BANK_behavioral_java_execution_count != 0):
            _fail("reflection_observation_invalid", "synthetic reads grant no candidate behavioral evidence")
        return mapping[runtime_owner], mapping[request.target.owner]
    _fail("reflection_authority_escalation", "this phase validates infrastructure observation receipts only")


def _issue_adapter_observation(request, *, runtime_class_identity, declaring_class_identity, canonical_value,
        runtime_identity, source_fingerprint, adapter_source_fingerprint, evidence_kind="synthetic_capability_fixture",
        measured_field_type="double", status="observed", failure_code="", timings=None):
    """Trusted internal bridge only, after a bounded adapter has performed a read.

    There is intentionally no public payload-to-receipt conversion. The caller
    is the phase-owned adapter verification bridge, never a model transport.
    """
    if type(request) is not ReadOnlyReflectionRequest:
        _fail("reflection_invalid", "validated typed request required by the internal adapter bridge")
    if evidence_kind != "synthetic_capability_fixture":
        _fail("reflection_authority_escalation", "this phase issues infrastructure receipts only; product execution is not admitted")
    measured = _timings(timings)
    began = perf_counter()
    tick = perf_counter()
    provenance = AdapterDiagnosticProvenance(ADAPTER_VERSION, adapter_source_fingerprint, source_fingerprint,
        runtime_identity, evidence_kind, False, 1, 0)
    _runtime_identities(request, provenance)
    if status == "observed":
        canonical_value = _canonical_bits(canonical_value)
    measured["value_normalization_seconds"] += perf_counter() - tick
    tick = perf_counter()
    observation = ReadOnlyReflectionObservation(request.fingerprint, _DESCRIPTOR.fingerprint,
        runtime_class_identity, declaring_class_identity, measured_field_type, canonical_value,
        status, failure_code, provenance)
    _validate_runtime_identities(request, observation)
    observation.fingerprint
    measured["observation_fingerprinting_seconds"] += perf_counter() - tick
    receipt = AdapterReadReceipt(observation, _receipt_signature(observation))
    measured["total_synthetic_diagnostic_overhead_seconds"] += perf_counter() - began
    return observation, receipt


def validate_read_only_reflection_observation(observation, *, request, adapter_receipt=None,
        capability_descriptor=None, timings=None, **request_lineage):
    """A matching adapter receipt proves origin; reconstruction proves binding."""
    try:
        payload = _payload(observation, ReadOnlyReflectionObservation, "observation_fingerprint")
        checked = validate_read_only_reflection_request(request, timings=timings, **request_lineage)
        descriptor = validate_read_only_reflection_capability_descriptor(
            _DESCRIPTOR if capability_descriptor is None else capability_descriptor)
        if not _receipt_authentic(adapter_receipt):
            _fail("reflection_observation_untrusted", "an independently issued bounded-adapter receipt is required")
        trusted = adapter_receipt.observation
        if _json(payload) != _json(trusted.as_dict()):
            _fail("reflection_observation_untrusted", "payload differs from the actual adapter read receipt")
        if trusted.request_fingerprint != checked.fingerprint or trusted.capability_descriptor_fingerprint != descriptor.fingerprint:
            _fail("reflection_target_stale", "observation request/descriptor binding differs")
        _validate_runtime_identities(checked, trusted)
        if trusted.status == "observed":
            if trusted.measured_field_type != checked.target.declared_type:
                _fail("reflection_target_mismatch", "exact measured field type differs")
            _canonical_bits(trusted.canonical_value)
        return trusted
    except ReadOnlyReflectionError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("reflection_observation_invalid", type(exc).__name__)


@dataclass(frozen=True, slots=True)
class DiagnosticCapabilityAvailability:
    execution_plan_fingerprint: str
    capability_descriptor_fingerprint: str
    capabilities: tuple[tuple[str, str], ...]
    status: str = field(default="execution_capability_incomplete", init=False)
    execution_authorized: bool = field(default=False, init=False)
    console_authorized: bool = field(default=False, init=False)
    behavior_validated: bool = field(default=False, init=False)
    first_remaining_blocker: str = field(default=FIRST_REMAINING_BLOCKER, init=False)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "availability_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def reconstruct_diagnostic_capability_availability(execution_plan, *, descriptor):
    """Separate architecture projection; the frozen historical plan is untouched."""
    checked = validate_read_only_reflection_capability_descriptor(descriptor)
    if type(execution_plan) is not planner.BehavioralEvidenceExecutionPlan:
        _fail("reflection_invalid", "typed historical execution plan required")
    planner._payload_gate(execution_plan.as_dict())
    capabilities = tuple(sorted((row.capability, checked.availability if row.capability == "read_only_reflection"
        else "unavailable" if row.capability == "deterministic_console_input" else row.status)
        for row in execution_plan.required_diagnostic_capabilities))
    return DiagnosticCapabilityAvailability(execution_plan.fingerprint, checked.fingerprint, capabilities)
