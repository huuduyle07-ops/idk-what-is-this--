"""Bounded measurement planning over the frozen oracle; never execution authority.

All acquisition and lineage checks belong to the frozen specification consumer.
This owner inspects only supplied post-state buffers, and emits no executable
source, commands, adapter implementation, or product API changes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from hashlib import sha256
import json
import math
from time import perf_counter

from core import behavioral_validation_specification as oracle
from core.structural_java import children, compact, get_parser, text

PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1"
SCHEMA_VERSION = "patch_candidate_behavior_exec_plan_1_v1"
FIRST_REMAINING_BLOCKER = "STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_NOT_IMPLEMENTED"
TIMING_FIELDS = ("spec_reconstruction_seconds", "candidate_inventory_analysis_seconds",
    "observability_path_selection_seconds", "scenario_minimization_seconds",
    "capability_classification_seconds", "plan_fingerprinting_seconds", "total_seconds")
MECHANISMS = frozenset({"direct_return", "direct_state_access", "existing_exact_state_query",
    "read_only_reflection", "compile_static_evidence", "deterministic_console_input", "unsupported_observation"})
CAPABILITIES = frozenset({"direct_public_invocation", "direct_return_observation", "existing_package_access",
    "direct_state_observation", "read_only_reflection", "deterministic_console_input",
    "unsupported_observation", "execution_setup_unavailable"})
CAPABILITY_STATES = frozenset({"available_by_existing_surface", "plannable_but_not_authorized", "unavailable", "unsupported"})
EVIDENCE_MODES = frozenset({"static_already_satisfied", "planned_runtime_evidence",
    "blocked_missing_capability", "blocked_semantic_gap"})
AUTHORITY_KEYS = oracle.AUTHORITY_KEYS | frozenset({"java_execution_authorized", "reflection_authorized",
    "console_authorized", "diagnostic_harness_generation_authorized"})
FORBIDDEN_PAYLOAD_KEYS = oracle.FORBIDDEN_PAYLOAD_KEYS | frozenset({"harness_source", "executable_source",
    "test_file", "executable_test_file", "field_set", "reflection_write", "getDeclaredFields",
    "arbitrary_accessibility_mutation", "state_mutation"})
MAX_PLAN_BYTES = 256_000
MAX_ITEMS = 64


class BehavioralExecutionPlanError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise BehavioralExecutionPlanError(code, reason)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _immutable(value):
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is tuple and len(value) <= MAX_ITEMS:
        for item in value:
            _immutable(item)
    elif is_dataclass(value) and value.__dataclass_params__.frozen:
        for descriptor in fields(value):
            _immutable(getattr(value, descriptor.name))
    else:
        _fail("execution_plan_invalid", "bounded immutable evidence required")


def _rows(value, kind):
    if type(value) is not tuple or len(value) > MAX_ITEMS or any(type(x) is not kind for x in value):
        _fail("execution_plan_invalid", "closed typed tuple required")


@dataclass(frozen=True, slots=True)
class ExactMemberBinding:
    path: str
    owner: str
    qualified_owner: str
    name: str
    kind: str
    declared_type: str
    parameters: tuple[tuple[str, str], ...]
    definition_id: str
    source_sha256: str
    definition_sha256: str
    visibility: str
    package_name: str

    @property
    def binary_owner(self):
        return (self.package_name + "." if self.package_name else "") + self.qualified_owner.replace("::", "$")

    def __post_init__(self):
        _immutable(self)
        if self.kind not in {"constructor", "method", "field"}:
            _fail("execution_plan_invalid", "exact member kind required")


@dataclass(frozen=True, slots=True)
class FixtureArgument:
    name: str
    declared_type: str
    value: str | float | int
    provenance: str
    evidence_ref: str

    def __post_init__(self):
        _immutable(self)
        if self.provenance not in {"diagnostic_fixture", "implementation_fixture"}:
            _fail("execution_plan_oracle_drift", "fixture values are never human semantics")
        if type(self.value) not in {str, int, float} or (type(self.value) is str and len(self.value) > 160):
            _fail("execution_plan_invalid", "bounded literal fixture required")


@dataclass(frozen=True, slots=True)
class PlannedInvocation:
    target: ExactMemberBinding
    arguments: tuple[FixtureArgument, ...]
    console_input: FixtureArgument | None = None
    expected_setup_return: bool | None = None

    def __post_init__(self):
        _immutable(self)
        _rows(self.arguments, FixtureArgument)
        if self.target.kind != "method":
            _fail("execution_plan_invalid", "bound method required")


@dataclass(frozen=True, slots=True)
class PlannedObservation:
    observation_id: str
    subject: str
    moment: str
    target: ExactMemberBinding | None
    mechanism: str
    required_capabilities: tuple[str, ...]
    reflection_operation: str = ""

    def __post_init__(self):
        _immutable(self)
        _rows(self.required_capabilities, str)
        if self.mechanism not in MECHANISMS or self.moment not in {"before", "after", "return"}:
            _fail("execution_plan_invalid", "closed observation route required")
        if self.reflection_operation not in {"", "read_exact_bound_field"}:
            _fail("execution_plan_authority_escalation", "reflection is read only")
        if self.mechanism == "read_only_reflection" and (self.target is None
                or self.target.kind != "field" or self.reflection_operation != "read_exact_bound_field"):
            _fail("execution_plan_invalid", "reflection requires an exact field")


@dataclass(frozen=True, slots=True)
class NumericComparisonPolicy:
    policy: str = field(default="absolute_plus_relative_tolerance", init=False)
    absolute_tolerance: float = field(default=1e-9, init=False)
    relative_tolerance: float = field(default=1e-12, init=False)
    finite_values_required: bool = field(default=True, init=False)
    relation: str = field(default="abs(actual-expected)<=absolute_tolerance+relative_tolerance*abs(expected)", init=False)
    provenance: str = field(default="diagnostic_implementation_policy", init=False)


@dataclass(frozen=True, slots=True)
class DiagnosticScenario:
    scenario_id: str
    purpose: str
    constructor: ExactMemberBinding | None
    constructor_arguments: tuple[FixtureArgument, ...]
    setup_invocations: tuple[PlannedInvocation, ...]
    invocation: PlannedInvocation | None
    observations: tuple[PlannedObservation, ...]
    obligation_ids: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    blockers: tuple[str, ...]
    comparison_policy: NumericComparisonPolicy
    isolation: str = field(default="fresh_candidate_instance", init=False)
    cleanup_requirement: str = field(default="discard_instance_and_ephemeral_harness_state", init=False)

    def __post_init__(self):
        _immutable(self)
        for name, kind in (("constructor_arguments", FixtureArgument), ("setup_invocations", PlannedInvocation),
                ("observations", PlannedObservation), ("obligation_ids", str), ("required_capabilities", str), ("blockers", str)):
            _rows(getattr(self, name), kind)
        if self.purpose not in {"wrong_credential_transfer", "wrong_credential_interest", "successful_transfer",
                "unsuccessful_debit", "savings_interest"}:
            _fail("execution_plan_oracle_drift", "closed scenario family required")


@dataclass(frozen=True, slots=True)
class DiagnosticCapability:
    capability: str
    status: str
    evidence_refs: tuple[str, ...]
    limitation: str

    def __post_init__(self):
        _immutable(self)
        _rows(self.evidence_refs, str)
        if self.capability not in CAPABILITIES or self.status not in CAPABILITY_STATES:
            _fail("execution_plan_invalid", "closed capability classification required")


@dataclass(frozen=True, slots=True)
class CapabilityBlocker:
    capability: str
    obligation_ids: tuple[str, ...]
    scenario_ids: tuple[str, ...]
    reason: str
    status: str = field(default="execution_capability_missing", init=False)


@dataclass(frozen=True, slots=True)
class ObligationExecutionPlan:
    obligation_id: str
    evidence_mode: str
    scenario_ids: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    blockers: tuple[str, ...]
    oracle: oracle.BehavioralObligation

    def __post_init__(self):
        _immutable(self)
        for name in ("scenario_ids", "required_capabilities", "blockers"):
            _rows(getattr(self, name), str)
        if self.evidence_mode not in EVIDENCE_MODES or type(self.oracle) is not oracle.BehavioralObligation:
            _fail("execution_plan_invalid", "bound obligation required")


@dataclass(frozen=True, slots=True)
class BehavioralEvidenceExecutionPlan:
    task_fingerprint: str
    effective_design_fingerprint: str
    implementation_plan_fingerprint: str
    admission_fingerprint: str
    candidate_fingerprint: str
    materialization_fingerprint: str
    compile_receipt_fingerprint: str
    behavioral_spec_fingerprint: str
    obligations: tuple[ObligationExecutionPlan, ...]
    scenarios: tuple[DiagnosticScenario, ...]
    required_diagnostic_capabilities: tuple[DiagnosticCapability, ...]
    static_satisfied_obligations: tuple[str, ...]
    unresolved_capability_blockers: tuple[CapabilityBlocker, ...]
    human_semantic_blockers: tuple[oracle.BehavioralOracleGap, ...]
    implementation_calculations: tuple[oracle.AdmittedInterestCalculation, ...]
    status: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    authority: str = field(default="behavioral_execution_plan_only", init=False)
    execution_authorized: bool = field(default=False, init=False)
    java_execution_authorized: bool = field(default=False, init=False)
    reflection_authorized: bool = field(default=False, init=False)
    console_authorized: bool = field(default=False, init=False)
    diagnostic_harness_generation_authorized: bool = field(default=False, init=False)
    test_write_authority: bool = field(default=False, init=False)
    write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    diagnostic_harness_required: bool = field(default=True, init=False)
    harness_kind: str = field(default="future_ephemeral_diagnostic_harness", init=False)
    reflection_rule: str = field(default="exact_field_lookup_and_read_only_no_enumeration_no_writes_no_private_invocation", init=False)
    console_rule: str = field(default="deterministic_console_attachment_required_stdin_pipe_is_not_equivalent", init=False)
    test_file_handling: str = field(default="proposed_product_test_paths_are_not_execution_targets", init=False)
    behavior_validated: bool = field(default=False, init=False)
    correctness_proven: bool = field(default=False, init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    javac_calls: int = field(default=0, init=False)
    java_execution_count: int = field(default=0, init=False)
    command_execution_count: int = field(default=0, init=False)
    reflection_execution_count: int = field(default=0, init=False)
    console_open_count: int = field(default=0, init=False)
    test_generation_count: int = field(default=0, init=False)
    diagnostic_harness_generation_count: int = field(default=0, init=False)
    source_mutation: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    first_remaining_blocker: str = field(default=FIRST_REMAINING_BLOCKER, init=False)

    def __post_init__(self):
        _immutable(self)
        for name, kind in (("obligations", ObligationExecutionPlan), ("scenarios", DiagnosticScenario),
                ("required_diagnostic_capabilities", DiagnosticCapability), ("static_satisfied_obligations", str),
                ("unresolved_capability_blockers", CapabilityBlocker), ("human_semantic_blockers", oracle.BehavioralOracleGap),
                ("implementation_calculations", oracle.AdmittedInterestCalculation)):
            _rows(getattr(self, name), kind)
        if self.status not in {"execution_ready", "execution_capability_incomplete", "execution_semantic_gap"}:
            _fail("execution_plan_invalid", "closed readiness required")

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    @property
    def execution_plan_fingerprint(self):
        return self.fingerprint

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "execution_plan_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _inventory(materialized, inputs):
    """Transient syntax bindings from named buffers, never field enumeration at runtime."""
    sources = oracle.compiler.materializer._sources(inputs)
    sources.update({f.path: f.after_bytes for f in materialized.virtual_files})
    rows, classes = {}, {}
    for path, raw in sorted(sources.items()):
        root = get_parser("java").parse(raw).root_node
        package = next((compact(children(n)[0], raw) for n in children(root) if n.type == "package_declaration"), "")
        def collect(node, owner=""):
            if node.type == "class_declaration":
                name = text(node.child_by_field_name("name"), raw)
                owner = (owner + "::" if owner else "") + name
                modifiers = next((n for n in children(node) if n.type == "modifiers"), None)
                tokens = [text(n, raw) for n in modifiers.children] if modifiers else []
                classes[(path, owner)] = (next((v for v in ("public", "protected", "private") if v in tokens), "package"), "static" in tokens)
                for child in children(node.child_by_field_name("body")):
                    collect(child, owner)
            elif node.type in {"method_declaration", "constructor_declaration", "field_declaration"}:
                kind = {"method_declaration": "method", "constructor_declaration": "constructor", "field_declaration": "field"}[node.type]
                modifiers = next((n for n in children(node) if n.type == "modifiers"), None)
                tokens = [text(n, raw) for n in modifiers.children] if modifiers else []
                visibility = next((v for v in ("public", "protected", "private") if v in tokens), "package")
                parameter_node = node.child_by_field_name("parameters")
                params = tuple((compact(p.child_by_field_name("type"), raw), text(p.child_by_field_name("name"), raw))
                    for p in children(parameter_node)) if parameter_node else ()
                names = [text(n.child_by_field_name("name"), raw) for n in children(node) if n.type == "variable_declarator"] if kind == "field" else [text(node.child_by_field_name("name"), raw)]
                for name in names:
                    key = (path, owner, name, kind)
                    rows.setdefault(key, []).append((ExactMemberBinding(path, owner.split("::")[-1], owner, name, kind,
                        compact(node.child_by_field_name("type"), raw), params, "existing:" + owner + "::" + name,
                        sha256(raw).hexdigest(), sha256(raw[node.start_byte:node.end_byte]).hexdigest(), visibility, package), node, raw))
            else:
                for child in children(node):
                    collect(child, owner)
        collect(root)
    return rows, classes


def _bound(target, inventory):
    from dataclasses import replace
    matches = [row for (path, qualified, name, kind), values in inventory[0].items()
        if (path, name, kind) == (target.path, target.name, target.kind) for row in values
        if target.qualified_owner in {qualified, (row[0].package_name.replace(".", "::") + "::" + qualified)
            if row[0].package_name else qualified}]
    # An overloaded name without an exact uniquely selected signature is blocked.
    if len(matches) != 1:
        return None
    return replace(matches[0][0], definition_id=target.definition_id)


def _entry(binding, inventory):
    matches = inventory[0].get((binding.path, binding.qualified_owner, binding.name, binding.kind), ())
    return next((x for x in matches if x[0].parameters == binding.parameters), None)


def _access(binding, inventory):
    parts = binding.qualified_owner.split("::")
    chain = [inventory[1].get((binding.path, "::".join(parts[:i])), ("private", False)) for i in range(1, len(parts) + 1)]
    if binding.visibility == "private" or any(v == "private" for v, _ in chain):
        return None
    return "direct_public_invocation" if binding.visibility == "public" and all(v == "public" for v, _ in chain) else "existing_package_access"


def _fixture(name, dtype, value, provenance="diagnostic_fixture", ref="bounded_synthetic_fixture_v1"):
    return FixtureArgument(name, dtype, value, provenance, ref)


def _setup(scope, spec, inventory):
    allowances = [a for a in scope.definition_allowances if "subclass_initialization" in a.definition.roles]
    transfer_targets = [t for o in spec.obligations if o.semantic_dimension == "authentication_gate" for t in o.target_definitions]
    if len(allowances) != 1 or not transfer_targets:
        return None, (), None
    d = allowances[0].definition
    owner = transfer_targets[0].qualified_owner
    target = oracle.BehavioralTargetDefinition(allowances[0].physical_target, d.owner, d.name, d.kind, d.identity, owner)
    ctor = _bound(target, inventory)
    if ctor is None or ctor.parameters != d.parameters or _access(ctor, inventory) is None:
        return None, (), None
    # Non-static inner classes need an enclosing instance; V1 does not invent one.
    if "::" in owner and not inventory[1].get((ctor.path, owner), ("", False))[1]:
        return None, (), None
    _, node, raw = _entry(ctor, inventory)
    statements = children(node.child_by_field_name("body"))
    super_calls = [n for n in statements if n.type == "explicit_constructor_invocation"]
    if len(super_calls) != 1:
        return None, (), None
    ordinary = next((t for o in spec.obligations for t in o.target_definitions if t.owner == "BankAccount" and t.name == "balance" and t.kind == "field"), None)
    base = _bound(ordinary, inventory) if ordinary else None
    if base is None:
        return None, (), None
    supplied = tuple(compact(n, raw) for n in children(super_calls[0].child_by_field_name("arguments")))
    # Match forwarded arguments by exact declared types, not parameter names.
    dtype_by_name = {n: t for t, n in ctor.parameters}
    base_ctors = [x for (path, qualified, _, kind), values in inventory[0].items()
        if path == base.path and qualified == base.qualified_owner and kind == "constructor" for x in values
        if tuple(t for t, _ in x[0].parameters) == tuple(dtype_by_name.get(p) for p in supplied)]
    if len(base_ctors) != 1:
        return None, (), None
    base_ctor, base_node, base_raw = base_ctors[0]
    body = children(base_node.child_by_field_name("body"))
    opening = [p for t, p in base_ctor.parameters if t in {"double", "float", "int", "long"}
        and any(compact(s, base_raw) in {"this.balance=" + p + ";", "balance=" + p + ";"} for s in body)]
    if len(opening) != 1 or any(s.type != "expression_statement" for s in body):
        return None, (), None
    assignments = [compact(s, base_raw) for s in body]
    allowed = {prefix + name + "=" + p + ";" for _, p in base_ctor.parameters
        for (path, qualified, name, kind) in inventory[0] if path == base.path and qualified == base.qualified_owner and kind == "field" for prefix in ("", "this.")}
    if not set(assignments) <= allowed:
        return None, (), None
    opening_param = supplied[[p for _, p in base_ctor.parameters].index(opening[0])]
    credential_names = {a.definition.name for a in scope.definition_allowances if "credential_state" in a.definition.roles}
    args = []
    for dtype, name in ctor.parameters:
        if name == opening_param:
            value = 1000.0 if dtype in {"double", "float"} else 1000
        elif dtype == "String":
            value = "exec-plan-correct" if name in credential_names else "exec-plan-holder"
        else:
            return None, (), None
        args.append(_fixture(name, dtype, value, ref="definition:" + base_ctor.definition_sha256
            if name == opening_param else "bounded_synthetic_fixture_v1"))
    return ctor, tuple(args), base_ctor.definition_sha256


def _observe(target, moment, inventory):
    binding = _bound(target, inventory)
    subject = target.owner + "::" + target.name
    if binding is None:
        return PlannedObservation(subject + "." + moment, subject, moment, None,
            "unsupported_observation", ("unsupported_observation",))
    if _access(binding, inventory):
        return PlannedObservation(subject + "." + moment, subject, moment, binding,
            "direct_state_access", ("direct_state_observation", "existing_package_access") if _access(binding, inventory) == "existing_package_access" else ("direct_state_observation",))
    # An exact zero-argument numeric query must return this precise field.
    queries = []
    for (path, qualified, _, kind), entries in inventory[0].items():
        if (path, qualified, kind) != (binding.path, binding.qualified_owner, "method"):
            continue
        for query, node, raw in entries:
            body = children(node.child_by_field_name("body"))
            if not query.parameters and query.declared_type == binding.declared_type and _access(query, inventory) and len(body) == 1 and compact(body[0], raw) in {"return" + binding.name + ";", "returnthis." + binding.name + ";"}:
                queries.append(query)
    if queries:
        query = sorted(queries, key=lambda x: x.name)[0]
        return PlannedObservation(subject + "." + moment, subject, moment, query,
            "existing_exact_state_query", ("direct_state_observation", _access(query, inventory)))
    return PlannedObservation(subject + "." + moment, subject, moment, binding,
        "read_only_reflection", ("read_only_reflection",), "read_exact_bound_field")


def _invocation(target, inventory, *, correct=True, amount=200.0, failure=False,
        setup=False, transfer_action=False, failure_evidence_ref=""):
    binding = _bound(target, inventory)
    if binding is None or _access(binding, inventory) is None:
        return None
    _, node, raw = _entry(binding, inventory)
    console = "System.console().readLine()" in compact(node.child_by_field_name("body"), raw)
    args = []
    numeric = 0
    for dtype, name in binding.parameters:
        if dtype == "String":
            value = "exec-plan-correct" if correct else "exec-plan-incorrect"
        elif dtype in {"double", "float", "int", "long"}:
            # Binary-exact rate works for both float and double parameters;
            # comparisons still use the bounded diagnostic tolerance policy.
            value = amount if transfer_action else (0.0625 if numeric == 0 else 2.0)
            numeric += 1
            if dtype in {"int", "long"} and int(value) != value:
                return None
            if dtype in {"int", "long"}:
                value = int(value)
        else:
            return None
        implementation_trigger = failure and dtype != "String"
        args.append(_fixture(name, dtype, value, "implementation_fixture" if implementation_trigger else "diagnostic_fixture",
            failure_evidence_ref if implementation_trigger else "bounded_synthetic_fixture_v1"))
    credential = _fixture("credential", "String", "exec-plan-correct" if correct else "exec-plan-incorrect") if console else None
    return PlannedInvocation(binding, tuple(args), credential, True if setup else None)


def _debit_trigger(spec, inventory):
    targets = [t for o in spec.obligations if o.semantic_dimension == "unsuccessful_debit_no_credit" for t in o.target_definitions if t.kind == "method" and t.owner == "BankAccount"]
    for target in targets:
        bound = _bound(target, inventory)
        if bound is None or bound.declared_type != "boolean" or len(bound.parameters) != 1:
            continue
        _, node, raw = _entry(bound, inventory)
        p = bound.parameters[0][1]
        syntax = compact(node.child_by_field_name("body"), raw)
        # Closed implementation witness; this trigger never becomes overdraft policy.
        witnesses = {"{if(" + a + "){" + b + "-=" + p + ";returntrue;}returnfalse;}"
            for a in (p + "<=balance", p + "<=this.balance", "balance>=" + p, "this.balance>=" + p) for b in ("balance", "this.balance")}
        if syntax in witnesses:
            return bound
    return None


def _project(spec, receipt, materialized, candidate, scope, inputs, measured):
    tick = perf_counter()
    inventory = _inventory(materialized, inputs)
    ctor, ctor_args, _ = _setup(scope, spec, inventory)
    debit = _debit_trigger(spec, inventory)
    measured["candidate_inventory_analysis_seconds"] += perf_counter() - tick
    tick = perf_counter()
    families = {o.semantic_dimension: o for o in spec.obligations if o.evidence_mode != "static_satisfied"}
    authentication = families.get("authentication_gate")
    transfers = tuple(t for t in authentication.target_definitions if t.kind == "method") if authentication else ()
    transfer = transfers[0] if transfers else None
    interest_obligation = families.get("savings_interest_target")
    interests = tuple(t for t in interest_obligation.target_definitions if t.kind == "method" and t.owner == "SavingAccount") if interest_obligation else ()
    state = {t.owner + "::" + t.name: t for o in spec.obligations for t in o.target_definitions if t.kind == "field" and t.name in {"balance", "savingBalance"}}
    drafts = []

    def scenario(purpose, target, family_names, *, correct=True, pre_transfer=False, failure=False):
        obligations = tuple(families[n] for n in family_names if n in families)
        if not obligations:
            return
        invoke = _invocation(target, inventory, correct=correct, amount=1001.0 if failure else 200.0,
            failure=failure, transfer_action=target in transfers,
            failure_evidence_ref="definition:" + debit.definition_sha256 if debit else "implementation_fixture_unavailable") if target else None
        setup = _invocation(transfer, inventory, setup=True, transfer_action=True) if pre_transfer and transfer else None
        observations = []
        subjects = sorted({c.subject for o in obligations for c in o.required_observation_capability if c.subject in state})
        # Do not add ordinary state requirements to failed-debit oracle.
        for subject in subjects:
            for moment in ("before", "after"):
                observations.append(_observe(state[subject], moment, inventory))
        if invoke and invoke.target.declared_type == "boolean":
            observations.append(PlannedObservation("transfer_return", invoke.target.owner + "::" + invoke.target.name,
                "return", invoke.target, "direct_return", ("direct_return_observation",)))
        required = {c for o in observations for c in o.required_capabilities}
        if ctor:
            required.add(_access(ctor, inventory))
        invocations = tuple(x for x in (setup, invoke) if x)
        for call in invocations:
            required.add(_access(call.target, inventory))
            if call.expected_setup_return is not None:
                required.add("direct_return_observation")
            if call.console_input:
                required.add("deterministic_console_input")
        if ctor is None or invoke is None or (pre_transfer and (setup is None or debit is None)) or (failure and debit is None) or (purpose == "successful_transfer" and debit is None):
            required.add("execution_setup_unavailable")
        drafts.append((purpose, ctor, ctor_args, (setup,) if setup else (), invoke, tuple(observations),
            tuple(o.obligation_id for o in obligations), tuple(sorted(required))))

    for target in transfers or (None,):
        scenario("wrong_credential_transfer", target, ("authentication_gate", "failed_auth_no_state_change"), correct=False)
    for target in interests:
        scenario("wrong_credential_interest", target, ("failed_auth_no_state_change",), correct=False, pre_transfer=True)
    for target in transfers or (None,):
        scenario("successful_transfer", target, ("successful_transfer_conservation",))
        scenario("unsuccessful_debit", target, ("unsuccessful_debit_no_credit",), failure=True)
    for target in interests:
        scenario("savings_interest", target, ("savings_interest_target",), pre_transfer=True)
    measured["observability_path_selection_seconds"] += perf_counter() - tick
    tick = perf_counter()
    # Shared wrong-transfer evidence covers two obligations; each other action
    # represents a different precondition or exact operation, using a fresh instance.
    drafts.sort(key=lambda d: (d[0], d[4].target.definition_id if d[4] else ""))
    measured["scenario_minimization_seconds"] += perf_counter() - tick
    tick = perf_counter()
    used = sorted({c for d in drafts for c in d[7]})
    capabilities = tuple(DiagnosticCapability(c,
        "plannable_but_not_authorized" if c == "read_only_reflection" else
        "unavailable" if c in {"deterministic_console_input", "execution_setup_unavailable"} else
        "unsupported" if c == "unsupported_observation" else "available_by_existing_surface",
        ("materialization:" + materialized.fingerprint,),
        "no_typed_read_only_reflection_adapter_or_execution_grant" if c == "read_only_reflection" else
        "no_typed_deterministic_console_adapter_stdin_pipe_is_insufficient" if c == "deterministic_console_input" else
        "exact_constructor_or_implementation_fixture_cannot_be_proven" if c == "execution_setup_unavailable" else
        "exact_state_target_unavailable" if c == "unsupported_observation" else "surface_availability_grants_no_execution_authority") for c in used)
    missing = {c.capability for c in capabilities if c.status != "available_by_existing_surface"}
    scenarios = tuple(DiagnosticScenario("BANK." + d[0] + ("." + str(i) if sum(x[0] == d[0] for x in drafts) > 1 else ""),
        *d[:7], d[7], tuple(c for c in d[7] if c in missing), NumericComparisonPolicy()) for i, d in enumerate(drafts))
    rows = []
    for obligation in spec.obligations:
        selected = tuple(s for s in scenarios if obligation.obligation_id in s.obligation_ids)
        # Each obligation owns only its observation requirements, even in a
        # shared scenario: authentication return does not require reflection.
        required = set()
        if obligation.evidence_mode != "static_satisfied":
            for scenario_row in selected:
                required.update(c for c in scenario_row.required_capabilities if c in {"direct_public_invocation", "existing_package_access", "deterministic_console_input", "execution_setup_unavailable"})
                subjects = {c.subject for c in obligation.required_observation_capability}
                required.update(c for observation in scenario_row.observations if observation.subject in subjects for c in observation.required_capabilities)
                if any(call.expected_setup_return is not None for call in scenario_row.setup_invocations):
                    required.add("direct_return_observation")
            if not selected:
                required.add("execution_setup_unavailable")
        blockers = tuple(sorted(required & missing))
        mode = "static_already_satisfied" if obligation.evidence_mode == "static_satisfied" else "blocked_semantic_gap" if spec.unresolved_oracle_gaps else "blocked_missing_capability" if blockers or not selected else "planned_runtime_evidence"
        rows.append(ObligationExecutionPlan(obligation.obligation_id, mode, tuple(s.scenario_id for s in selected), tuple(sorted(required)), blockers, obligation))
    blockers = tuple(CapabilityBlocker(c.capability, tuple(r.obligation_id for r in rows if c.capability in r.blockers),
        tuple(s.scenario_id for s in scenarios if c.capability in s.blockers), c.limitation) for c in capabilities if c.capability in missing)
    measured["capability_classification_seconds"] += perf_counter() - tick
    return BehavioralEvidenceExecutionPlan(spec.task_fingerprint, spec.effective_design_fingerprint,
        spec.implementation_plan_fingerprint, spec.admission_fingerprint, spec.candidate_fingerprint,
        spec.materialization_fingerprint, spec.compile_receipt_fingerprint, spec.fingerprint,
        tuple(rows), scenarios, capabilities, tuple(o.obligation_id for o in spec.obligations if o.evidence_mode == "static_satisfied"),
        blockers, spec.unresolved_oracle_gaps, spec.implementation_calculations,
        "execution_semantic_gap" if spec.unresolved_oracle_gaps else
        "execution_capability_incomplete" if blockers else "execution_ready")


def _payload_gate(payload):
    if type(payload) is dict:
        for key, value in payload.items():
            if key == "authority" and value != "behavioral_execution_plan_only":
                _fail("execution_plan_authority_escalation", key)
            if key in AUTHORITY_KEYS and value is not False:
                _fail("execution_plan_authority_escalation", key)
            if key in {"field_set", "reflection_write", "state_mutation", "arbitrary_accessibility_mutation"} or (key == "reflection_operation" and value not in {"", "read_exact_bound_field"}):
                _fail("execution_plan_authority_escalation", "reflection is read only")
            if key in FORBIDDEN_PAYLOAD_KEYS:
                _fail("execution_plan_invalid", "no executable payloads or commands")
            _payload_gate(value)
    elif type(payload) in {tuple, list}:
        if len(payload) > MAX_ITEMS:
            _fail("execution_plan_invalid", "collection bound")
        for item in payload:
            _payload_gate(item)


def _run(specification, compile_receipt, materialized, candidate, admitted_scope, inputs, measured):
    tick = perf_counter()
    try:
        spec = oracle.validate_behavioral_validation_specification(specification,
            compile_receipt=compile_receipt, materialized=materialized, candidate=candidate,
            admitted_scope=admitted_scope, **inputs)
    except oracle.BehavioralSpecificationError as exc:
        _fail("execution_plan_unavailable" if exc.code == "behavior_spec_unavailable_due_compile_failure" else
            "execution_plan_stale" if exc.code == "behavior_spec_stale" else "execution_plan_invalid", exc.code + ": " + exc.reason)
    finally:
        measured["spec_reconstruction_seconds"] += perf_counter() - tick
    plan = _project(spec, compile_receipt, materialized, candidate, admitted_scope, inputs, measured)
    tick = perf_counter()
    payload = plan.as_dict()
    if len(_json(payload).encode("utf-8")) > MAX_PLAN_BYTES:
        _fail("execution_plan_invalid", "execution plan byte bound")
    measured["plan_fingerprinting_seconds"] += perf_counter() - tick
    return plan


def build_behavioral_evidence_execution_plan(specification, *, compile_receipt, materialized,
        candidate, admitted_scope, timings=None, **fresh_inputs):
    """Pure planning: first reconstruct the full oracle/compile/candidate lineage."""
    measured = {} if timings is None else timings
    measured.update({key: 0.0 for key in TIMING_FIELDS})
    began = perf_counter()
    try:
        return _run(specification, compile_receipt, materialized, candidate, admitted_scope, fresh_inputs, measured)
    except BehavioralExecutionPlanError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("execution_plan_invalid", type(exc).__name__)
    finally:
        measured["total_seconds"] = perf_counter() - began


def validate_behavioral_evidence_execution_plan(execution_plan, *, specification, compile_receipt,
        materialized, candidate, admitted_scope, timings=None, **fresh_inputs):
    """Canonical independent reconstruction; no UI/session or hash-only trust."""
    measured = {} if timings is None else timings
    measured.update({key: 0.0 for key in TIMING_FIELDS})
    began = perf_counter()
    try:
        payload = execution_plan.as_dict() if type(execution_plan) is BehavioralEvidenceExecutionPlan else execution_plan
        if type(payload) is not dict or len(_json(payload).encode("utf-8")) > MAX_PLAN_BYTES:
            _fail("execution_plan_invalid", "bounded closed execution plan required")
        _payload_gate(payload)
        if set(payload) != {f.name for f in fields(BehavioralEvidenceExecutionPlan)} | {"execution_plan_fingerprint"}:
            _fail("execution_plan_invalid", "closed execution plan schema required")
        rebuilt = _run(specification, compile_receipt, materialized, candidate, admitted_scope, fresh_inputs, measured)
        if _json(payload) != _json(rebuilt.as_dict()):
            _fail("execution_plan_stale", "canonical oracle, mechanisms, fixtures, capabilities or lineage differs")
        return rebuilt
    except BehavioralExecutionPlanError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("execution_plan_invalid", type(exc).__name__)
    finally:
        measured["total_seconds"] = perf_counter() - began


project_behavioral_evidence_execution_plan = build_behavioral_evidence_execution_plan
