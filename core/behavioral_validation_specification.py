"""PATCH.CANDIDATE.BEHAVIOR.SPEC.1: an oracle, never a test or execution grant.

Reconstruct the frozen receipts using supplied typed evidence, then project the
closed BANK behavior vocabulary. Source inspection is confined to bound buffers
and establishes observation capabilities; it never creates domain intent.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from hashlib import sha256
import json
from time import perf_counter

from core import structural_compile_validation as compiler
from core.structural_java import children, compact, get_parser, text

PHASE_ID = "PATCH.CANDIDATE.BEHAVIOR.SPEC.1"
SCHEMA_VERSION = "patch_candidate_behavior_spec_1_v1"
FIRST_REMAINING_BLOCKER = "STRUCTURAL_CANDIDATE_BEHAVIORAL_EXECUTION_PLANNING_NOT_IMPLEMENTED"
TIMING_FIELDS = ("compile_receipt_reconstruction_seconds", "semantic_coverage_projection_seconds",
    "observability_analysis_seconds", "obligation_normalization_seconds",
    "fingerprint_construction_seconds", "total_seconds")
OBLIGATION_FAMILIES = frozenset({"authentication_gate", "failed_auth_no_state_change",
    "successful_transfer_conservation", "unsuccessful_debit_no_credit", "savings_interest_target",
    "credential_lifecycle", "base_savings_transition"})
EVIDENCE_MODES = frozenset({"static_satisfied", "runtime_required", "unresolved_observability"})
PRECONDITIONS = frozenset({"incorrect_credential", "correct_credential", "successful_inherited_debit",
    "unsuccessful_inherited_debit", "transfer_amount_A", "distinct_ordinary_and_savings_principals",
    "admitted_interest_parameters", "bound_candidate_only", "chosen_base_transition"})
ACTIONS = frozenset({"request_savings_transfer", "request_each_savings_operation",
    "request_savings_interest", "inspect_scoped_credential_dependencies", "observe_base_savings_transition"})
OBSERVATIONS = frozenset({"transfer_returns_false", "ordinary_balance_unchanged",
    "savings_balance_unchanged", "ordinary_balance_decreases_by_A", "savings_balance_increases_by_A",
    "ordinary_plus_savings_total_conserved", "savings_balance_not_increased",
    "candidate_selected_simple_interest_on_savings_principal", "no_persistent_credential_dependency_in_admitted_candidate",
    "subclass_savings_available_without_retired_base_operation", "base_savings_semantically_available",
    "subclass_specialization_acts_on_savings_balance", "protected_transition_after_failed_verification",
    "savings_credit_after_unsuccessful_debit", "ordinary_balance_used_as_interest_principal",
    "retired_base_operation_required_for_subclass_savings"})
CAPABILITIES = frozenset({"method_return", "visible_field", "existing_exact_state_query",
    "reflection_required", "compile_static_evidence_only", "existing_package_behavior",
    "existing_public_behavior", "observation_path_missing"})
AUTHORITY_KEYS = frozenset({"test_write_authority", "execution_authorized", "write_authority",
    "apply_authority", "filesystem_write_authority", "filesystem_file_creation_authority", "auto_apply"})
FORBIDDEN_PAYLOAD_KEYS = frozenset({"test_code", "test_source", "java_source", "junit_source",
    "assertion_code", "source_text", "code", "commands", "command", "java_command", "javac_command",
    "junit_invocation", "shell_command", "execution_environment", "repository_root"})
MAX_SPEC_BYTES = 128_000
MAX_ITEMS = 64


class BehavioralSpecificationError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise BehavioralSpecificationError(code, reason)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _immutable(value):
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is tuple and len(value) <= MAX_ITEMS:
        for item in value:
            _immutable(item)
    elif is_dataclass(value) and value.__dataclass_params__.frozen:
        for descriptor in fields(value):
            _immutable(getattr(value, descriptor.name))
    else:
        _fail("behavior_spec_invalid", "bounded immutable evidence required")


def _rows(value, kind):
    if type(value) is not tuple or len(value) > MAX_ITEMS or any(type(x) is not kind for x in value):
        _fail("behavior_spec_invalid", "closed typed tuple required")


@dataclass(frozen=True, slots=True)
class BehavioralProvenance:
    kind: str
    dimension: str
    value: str
    evidence_ref: str

    def __post_init__(self):
        _immutable(self)
        if self.kind not in {"explicit_human", "implementation_contract", "measured_structural"}:
            _fail("behavior_spec_invalid", "closed provenance required")


@dataclass(frozen=True, slots=True)
class BehavioralTargetDefinition:
    path: str
    owner: str
    name: str
    kind: str
    definition_id: str
    qualified_owner: str = ""


@dataclass(frozen=True, slots=True)
class ObservationCapability:
    subject: str
    capability: str
    available: bool
    evidence_refs: tuple[str, ...]
    limitation: str = ""

    def __post_init__(self):
        _immutable(self)
        _rows(self.evidence_refs, str)
        if self.capability not in CAPABILITIES or type(self.available) is not bool:
            _fail("behavior_spec_invalid", "closed observation capability required")


@dataclass(frozen=True, slots=True)
class BehavioralObligation:
    obligation_id: str
    semantic_dimension: str
    preconditions: tuple[str, ...]
    action: str
    expected_observations: tuple[str, ...]
    forbidden_observations: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    target_definitions: tuple[BehavioralTargetDefinition, ...]
    materialization_hashes: tuple[tuple[str, str], ...]
    required_observation_capability: tuple[ObservationCapability, ...]
    provenance: tuple[BehavioralProvenance, ...]
    evidence_mode: str
    status: str
    materiality: str = field(default="required", init=False)

    def __post_init__(self):
        _immutable(self)
        for name in ("preconditions", "expected_observations", "forbidden_observations", "evidence_refs"):
            _rows(getattr(self, name), str)
        _rows(self.target_definitions, BehavioralTargetDefinition)
        _rows(self.required_observation_capability, ObservationCapability)
        _rows(self.provenance, BehavioralProvenance)
        if (self.semantic_dimension not in OBLIGATION_FAMILIES or self.action not in ACTIONS
                or not set(self.preconditions) <= PRECONDITIONS
                or not set((*self.expected_observations, *self.forbidden_observations)) <= OBSERVATIONS
                or self.evidence_mode not in EVIDENCE_MODES or self.status != {
                    "static_satisfied": "static_satisfied", "runtime_required": "runtime_required",
                    "unresolved_observability": "observation_evidence_missing"}[self.evidence_mode]):
            _fail("behavior_spec_invalid", "closed obligation vocabulary required")


@dataclass(frozen=True, slots=True)
class BehavioralCoverage:
    semantic_dimension: str
    obligation_ids: tuple[str, ...]
    evidence_mode: str
    status: str


@dataclass(frozen=True, slots=True)
class BehavioralEvidenceRequirement:
    obligation_id: str
    evidence_mode: str
    observation_subjects: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BehavioralObservationGap:
    obligation_ids: tuple[str, ...]
    subject: str
    required_capability: str
    status: str = field(default="observation_evidence_missing", init=False)


@dataclass(frozen=True, slots=True)
class ExecutionHarnessConstraint:
    obligation_ids: tuple[str, ...]
    target_definitions: tuple[BehavioralTargetDefinition, ...]
    capability: str = field(default="console_input", init=False)
    reason: str = field(default="System.console_requires_console", init=False)
    status: str = field(default="execution_harness_constraint", init=False)


@dataclass(frozen=True, slots=True)
class BehavioralOracleGap:
    semantic_dimension: str
    missing_human_decision: str
    evidence_refs: tuple[str, ...]
    status: str = field(default="behavioral_semantic_gap", init=False)


@dataclass(frozen=True, slots=True)
class AdmittedInterestCalculation:
    """Closed selected operation, with parameter order from the admitted PLAN.

    This describes the frozen implementation contract, not a domain formula.
    It carries no source expression and no scheduling or financial policy.
    """
    definition_id: str
    principal: str
    parameter_names: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    operation: str = field(default="add_principal_times_selected_parameters", init=False)
    provenance: str = field(default="implementation_contract", init=False)


@dataclass(frozen=True, slots=True)
class BehavioralValidationSpecification:
    task_fingerprint: str
    effective_design_fingerprint: str
    implementation_plan_fingerprint: str
    admission_fingerprint: str
    candidate_fingerprint: str
    materialization_fingerprint: str
    compile_receipt_fingerprint: str
    base_savings_transition: str
    obligations: tuple[BehavioralObligation, ...]
    coverage: tuple[BehavioralCoverage, ...]
    evidence_requirements: tuple[BehavioralEvidenceRequirement, ...]
    unresolved_oracle_gaps: tuple[BehavioralOracleGap, ...]
    observation_gaps: tuple[BehavioralObservationGap, ...]
    execution_harness_constraints: tuple[ExecutionHarnessConstraint, ...]
    implementation_calculations: tuple[AdmittedInterestCalculation, ...]
    proposed_test_files: tuple[str, ...]
    status: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    authority: str = field(default="behavioral_oracle_only", init=False)
    test_write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    behavior_validated: bool = field(default=False, init=False)
    correctness_proven: bool = field(default=False, init=False)
    behavioral_validation_pending: bool = field(default=True, init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    source_mutation: int = field(default=0, init=False)
    test_generation_count: int = field(default=0, init=False)
    java_execution_count: int = field(default=0, init=False)
    command_execution_count: int = field(default=0, init=False)
    first_remaining_blocker: str = field(default=FIRST_REMAINING_BLOCKER, init=False)

    def __post_init__(self):
        _immutable(self)
        for name, kind in (("obligations", BehavioralObligation), ("coverage", BehavioralCoverage),
                ("evidence_requirements", BehavioralEvidenceRequirement), ("unresolved_oracle_gaps", BehavioralOracleGap),
                ("observation_gaps", BehavioralObservationGap), ("execution_harness_constraints", ExecutionHarnessConstraint),
                ("implementation_calculations", AdmittedInterestCalculation),
                ("proposed_test_files", str)):
            _rows(getattr(self, name), kind)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    @property
    def behavioral_spec_fingerprint(self):
        return self.fingerprint

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "behavioral_spec_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _reconstruct(compile_receipt, materialized, candidate, admitted_scope, inputs, measured):
    tick = perf_counter()
    try:
        # A root is intentionally not accepted: SPEC.1 has no acquisition seam.
        if "repository_root" in inputs:
            _fail("behavior_spec_invalid", "only bound evidence buffers are consumed")
        checked = compiler.validate_structural_compile_receipt(compile_receipt,
            materialized=materialized, candidate=candidate, admitted_scope=admitted_scope, **inputs)
    except compiler.CompileValidationError as exc:
        _fail("behavior_spec_stale", exc.code + ": " + exc.reason)
    finally:
        measured["compile_receipt_reconstruction_seconds"] += perf_counter() - tick
    if checked.status != "compile_validated" or checked.compile_success is not True:
        _fail("behavior_spec_unavailable_due_compile_failure", checked.status)
    return checked


def _ref(kind, value):
    return kind + ":" + _hash(asdict(value))


def _targets(scope, inputs, *roles):
    targets = []
    for allowance in scope.definition_allowances:
        definition = allowance.definition
        if not set(definition.roles) & set(roles):
            continue
        qualified = definition.owner
        contexts = [c for c, _ in compiler.materializer._pairs(inputs)
            if c.file == allowance.physical_target and c.class_identity.name == definition.owner]
        if contexts:
            qualified = contexts[0].class_identity.qualified_name.replace(".", "::")
        if allowance.physical_layout == "nested_in_parent":
            containers = [o for o in scope.permitted_structural_operations
                if o.operation == "insert_nested_class" and definition.identity in o.definition_ids]
            if len(containers) != 1:
                _fail("behavior_spec_stale", "exact nested owner missing")
            container = containers[0]
            parents = [c for c, _ in compiler.materializer._pairs(inputs)
                if c.file == allowance.physical_target and c.class_identity.name == container.owner]
            if len(parents) != 1:
                _fail("behavior_spec_stale", "ambiguous nested class container")
            qualified = parents[0].class_identity.qualified_name.replace(".", "::") + "::" + definition.owner
        targets.append(BehavioralTargetDefinition(allowance.physical_target, definition.owner,
            definition.name, definition.kind, definition.identity, qualified))
    return tuple(sorted(targets, key=lambda t: (t.path, t.qualified_owner, t.name, t.kind)))


def _observation_inventory(materialized, inputs):
    """Inspect only exact bound post-state buffers, including untouched support.

    A direct zero-argument numeric field query is sufficient. Textual display,
    computed values and boolean success are not exact state observations.
    """
    rows = compiler.materializer._sources(inputs)
    rows.update({f.path: f.after_bytes for f in materialized.virtual_files})
    inventory = {}
    for path, raw in sorted(rows.items()):
        root = get_parser("java").parse(raw).root_node
        def collect(node, owner=""):
            if node.type in {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"}:
                owner = (owner + "::" if owner else "") + text(node.child_by_field_name("name"), raw)
                modifiers = next((n for n in children(node) if n.type == "modifiers"), None)
                tokens = [text(n, raw) for n in modifiers.children] if modifiers else []
                visibility = next((v for v in ("public", "protected", "private") if v in tokens), "package")
                inventory[(path, owner, "", "class")] = (visibility, (), False, "")
                for child in children(node.child_by_field_name("body")):
                    collect(child, owner)
            elif node.type in {"field_declaration", "method_declaration"}:
                modifiers = next((n for n in children(node) if n.type == "modifiers"), None)
                tokens = [text(n, raw) for n in modifiers.children] if modifiers else []
                visibility = next((v for v in ("public", "protected", "private") if v in tokens), "package")
                if node.type == "field_declaration":
                    for declaration in children(node):
                        if declaration.type == "variable_declarator":
                            name = text(declaration.child_by_field_name("name"), raw)
                            inventory[(path, owner, name, "field")] = (visibility, (), False, "")
                else:
                    name = text(node.child_by_field_name("name"), raw)
                    params = children(node.child_by_field_name("parameters"))
                    body = node.child_by_field_name("body")
                    statements = children(body) if body else []
                    query = ""
                    if (not params and len(statements) == 1 and statements[0].type == "return_statement"
                            and compact(node.child_by_field_name("type"), raw) in {"double", "float", "int", "long"}):
                        values = children(statements[0])
                        if len(values) == 1 and values[0].type in {"identifier", "field_access"}:
                            value = compact(values[0], raw)
                            if "." not in value or value.startswith("this."):
                                query = value.removeprefix("this.")
                    console = "System.console().readLine()" in compact(body, raw)
                    inventory[(path, owner, name, "method")] = (visibility, tuple(compact(p, raw) for p in params), console, query)
            else:
                for child in children(node):
                    collect(child, owner)
        collect(root)
    return inventory


def _owner_accessible(target, inventory):
    parts = target.qualified_owner.split("::")
    return all(inventory.get((target.path, "::".join(parts[:index]), "", "class"), ("private",))[0] != "private"
        for index in range(1, len(parts) + 1))


def _state_capability(target, inventory, materialized):
    subject = target.owner + "::" + target.name
    ref = "materialization:" + materialized.fingerprint
    field_info = inventory.get((target.path, target.qualified_owner, target.name, "field"))
    if not _owner_accessible(target, inventory):
        return ObservationCapability(subject, "reflection_required", False, (ref,),
            "private_class_without_existing_authorized_access")
    if field_info is not None and field_info[0] != "private":
        return ObservationCapability(subject, "visible_field", True, (ref,),
            "same_class_or_package_harness_requires_separate_authorization")
    queries = [(path, owner, name) for (path, owner, name, kind), info in inventory.items()
        if kind == "method" and path == target.path and owner == target.qualified_owner
        and info[0] != "private" and info[3] == target.name]
    if queries:
        path, owner, name = sorted(queries)[0]
        return ObservationCapability(subject, "existing_exact_state_query", True,
            (ref, "existing_query:" + path + ":" + owner + "::" + name))
    return ObservationCapability(subject, "reflection_required" if field_info is not None else "observation_path_missing",
        False, (ref,), "private_state_without_existing_exact_query" if field_info is not None else "exact_state_definition_unavailable")


def _project(checked, materialized, candidate, scope, inputs, measured):
    tick = perf_counter()
    design, plan = inputs["scope_transition_effective_design"], inputs["plan"]
    facts = {x.dimension: x for x in design.parent.continuation.typed_answer_commitments}
    transition = design.existing_savings_transition
    # These values were already validated upstream. Unknown semantics are never
    # converted into assertions by reading task prose or candidate syntax.
    required = {"credential_ownership": "SavingAccount", "credential_persistence": "in_memory_only",
        "verification_lifecycle": "operation_gated", "savings_funding_semantics": "transfer_from_inherited_balance",
        "savings_interest_semantics": "interest_applies_to_saving_balance"}
    gaps = tuple(BehavioralOracleGap(dim, "typed_behavior_commitment_required", ("design:" + design.fingerprint,))
        for dim, value in required.items() if dim not in facts or facts[dim].value != value)
    if gaps:
        measured["semantic_coverage_projection_seconds"] += perf_counter() - tick
        return _spec(checked, materialized, candidate, scope, plan, transition, (), (), (), gaps, (), (),
            (), "behavioral_semantic_gap")
    human = {dim: BehavioralProvenance("explicit_human", dim, item.value, _ref("human_commitment", item))
        for dim, item in facts.items()}
    gate_provenance = tuple(BehavioralProvenance(g.evidence.provenance, "successful_verification_gate", g.condition,
        _ref("human_gate", g)) for g in design.behavior_gates)
    transition_fact = design.transition.typed_answer_commitments[0]
    transition_provenance = BehavioralProvenance("explicit_human", "existing_savings_transition", transition,
        _ref("human_transition", transition_fact))
    definitions = {a.definition.identity: a.definition for a in scope.definition_allowances}
    transfer = _targets(scope, inputs, "savings_funding_transition")
    interest = _targets(scope, inputs, "savings_interest_behavior")
    savings = _targets(scope, inputs, "subclass_owned_state")
    credential = _targets(scope, inputs, "credential_state")
    debit = _targets(scope, inputs, "base_balance_debit")
    existing_debits = tuple(binding for coverage in scope.capability_coverage if coverage.code == "base_balance_debit"
        for binding in coverage.existing_mechanisms)
    debit += tuple(BehavioralTargetDefinition(binding.file, binding.owner, binding.name, binding.kind,
        "existing:" + binding.owner + "::" + binding.name, next((c.class_identity.qualified_name.replace(".", "::")
        for c, _ in compiler.materializer._pairs(inputs) if c.file == binding.file and c.class_identity.name == binding.owner),
        binding.owner)) for binding in existing_debits)
    if not all((transfer, interest, savings, credential)):
        _fail("behavior_spec_stale", "required admitted capabilities absent")
    base_contexts = [context for context, _ in compiler.materializer._pairs(inputs)
        if context.class_identity.name == "BankAccount"]
    ordinary = tuple(BehavioralTargetDefinition(c.file, c.class_identity.name, f.name, "field",
        "existing:" + c.class_identity.name + "::" + f.name, c.class_identity.qualified_name.replace(".", "::"))
        for c in base_contexts for f in c.fields if f.name == "balance")
    measured["semantic_coverage_projection_seconds"] += perf_counter() - tick
    tick = perf_counter()
    inventory = _observation_inventory(materialized, inputs)
    state_caps = tuple(_state_capability(t, inventory, materialized) for t in (*ordinary, *savings))
    if not ordinary:
        state_caps = (ObservationCapability("BankAccount::balance", "observation_path_missing", False,
            ("materialization:" + materialized.fingerprint,), "exact_state_definition_unavailable"), *state_caps)
    savings_caps = tuple(c for c in state_caps if c.subject.startswith(savings[0].owner + "::"))
    return_caps = tuple(ObservationCapability(t.owner + "::" + t.name, "method_return",
        definitions[t.definition_id].declared_type == "boolean" and definitions[t.definition_id].visibility != "private"
        and _owner_accessible(t, inventory),
        ("plan:" + plan.fingerprint,), "boolean_result_does_not_prove_state_conservation") for t in transfer)
    console_targets = tuple(t for t in (*transfer, *interest)
        if inventory.get((t.path, t.qualified_owner, t.name, "method"), ("", (), False, ""))[2])
    static_cap = (ObservationCapability("admitted_candidate", "compile_static_evidence_only", True,
        ("materialization:" + materialized.fingerprint, "candidate:" + candidate.fingerprint)),)
    measured["observability_analysis_seconds"] += perf_counter() - tick
    tick = perf_counter()
    obligations = []
    common_refs = ("compile_receipt:" + checked.fingerprint, "materialization:" + materialized.fingerprint,
        "plan:" + plan.fingerprint, *(_ref("validation_need", n) for n in scope.validation_evidence_needs
        if n.kind != "javac"))
    hashes = tuple((f.path, f.after_sha256) for f in materialized.virtual_files) + tuple(
        (f.path, f.source_sha256) for f in materialized.supporting_files)

    def contract(dimension, value):
        return BehavioralProvenance("implementation_contract", dimension, value, "plan:" + plan.fingerprint)

    def add(family, preconditions, action, expected, forbidden, targets, capabilities, provenance, static=False):
        mode = "static_satisfied" if static else "runtime_required" if all(c.available for c in capabilities) else "unresolved_observability"
        status = "observation_evidence_missing" if mode == "unresolved_observability" else mode
        obligations.append(BehavioralObligation("BANK." + family, family, tuple(preconditions), action,
            tuple(expected), tuple(forbidden), tuple(sorted(set((*common_refs, *(p.evidence_ref for p in provenance))))),
            tuple(sorted(set(targets), key=lambda t: (t.path, t.owner, t.name, t.kind))), tuple(sorted(hashes)),
            tuple(capabilities), tuple(provenance), mode, status))

    add("authentication_gate", ("incorrect_credential",), "request_savings_transfer",
        ("transfer_returns_false",), (), transfer, return_caps,
        (*gate_provenance, human["verification_lifecycle"],
         contract("transfer_result", "boolean_failure_after_failed_verification")))
    add("failed_auth_no_state_change", ("incorrect_credential",), "request_each_savings_operation",
        ("ordinary_balance_unchanged", "savings_balance_unchanged"), ("protected_transition_after_failed_verification",),
        (*transfer, *interest, *ordinary, *savings), state_caps,
        (*gate_provenance, human["verification_lifecycle"], human["savings_funding_semantics"]))
    add("successful_transfer_conservation", ("correct_credential", "successful_inherited_debit", "transfer_amount_A"),
        "request_savings_transfer", ("ordinary_balance_decreases_by_A", "savings_balance_increases_by_A",
        "ordinary_plus_savings_total_conserved"), (), (*transfer, *debit, *ordinary, *savings), state_caps,
        (human["savings_funding_semantics"], contract("savings_credit_guard", scope.savings_credit_guard)))
    add("unsuccessful_debit_no_credit", ("correct_credential", "unsuccessful_inherited_debit"),
        "request_savings_transfer", ("savings_balance_not_increased", "transfer_returns_false"),
        ("savings_credit_after_unsuccessful_debit",), (*transfer, *debit, *savings), (*savings_caps, *return_caps),
        (contract("savings_credit_guard", scope.savings_credit_guard), human["savings_funding_semantics"]))
    # Frozen AUTHOR validates the closed simple-rate operation against each
    # admitted interest definition. Reuse that implementation contract and typed
    # parameter order; do not parse planner rationale or derive human intent from
    # the candidate's source. Formula details remain implementation-owned.
    decisions = tuple(d for d in scope.implementation_decisions if d.area == "savings_interest")
    if not decisions or any(definitions[t.definition_id].contract != "interest_on_saving_balance_only"
            or not definitions[t.definition_id].parameters for t in interest):
        _fail("behavior_spec_stale", "admitted interest implementation contract missing")
    calculations = tuple(AdmittedInterestCalculation(t.definition_id, savings[0].owner + "::" + savings[0].name,
        tuple(name for _, name in definitions[t.definition_id].parameters[:2]),
        ("plan:" + plan.fingerprint, "candidate:" + candidate.fingerprint, "materialization:" + materialized.fingerprint,
         *(_ref("implementation_decision", d) for d in decisions))) for t in interest)
    add("savings_interest_target", ("correct_credential", "distinct_ordinary_and_savings_principals", "admitted_interest_parameters"),
        "request_savings_interest", ("candidate_selected_simple_interest_on_savings_principal", "ordinary_balance_unchanged"),
        ("ordinary_balance_used_as_interest_principal",),
        (*interest, *ordinary, *savings), state_caps, (human["savings_interest_semantics"],
        contract("savings_interest_calculation", "admitted_simple_rate_operation")))
    add("credential_lifecycle", ("bound_candidate_only",), "inspect_scoped_credential_dependencies",
        ("no_persistent_credential_dependency_in_admitted_candidate",), (), credential, static_cap,
        (human["credential_ownership"], human["credential_persistence"],
         *(human[dim] for dim in ("credential_source", "credential_verification_mechanism", "exercise_hashing_constraint") if dim in human),
         BehavioralProvenance("measured_structural", "credential_dependencies", "scoped_in_memory_only",
             "candidate:" + candidate.fingerprint)), static=True)
    existing_base = tuple(BehavioralTargetDefinition(c.file, "BankAccount", m.name, "method",
        "existing:BankAccount::" + m.name, c.class_identity.qualified_name.replace(".", "::"))
        for c in base_contexts for m in c.methods if m.name == "saving")
    if transition == "savings_only_on_subclass":
        # Structural absence plus independent subclass operations satisfies this
        # API ownership fact; no runtime method-deletion assertion is produced.
        add("base_savings_transition", ("chosen_base_transition",), "observe_base_savings_transition",
            ("subclass_savings_available_without_retired_base_operation",),
            ("retired_base_operation_required_for_subclass_savings",), (*transfer, *interest), static_cap,
            (transition_provenance, contract("base_saving_action", scope.base_saving_action)), static=True)
    else:
        preserved = tuple(p for p in materialized.supporting_declarations if p.owner == "BankAccount"
            and p.name == "saving" and p.kind == "method" and p.mode == "exact_declaration")
        if not existing_base or not preserved or any(
                not any((p.path, p.owner, p.name) == (t.path, t.owner, t.name) for p in preserved) for t in existing_base):
            _fail("behavior_spec_stale", "preserved base contract unavailable")
        # Both transitions retain the same already-proven base contract. The
        # specialization's action on savings state is the interest obligation;
        # coverage links it here rather than requiring a redundant second proof.
        add("base_savings_transition", ("chosen_base_transition",), "observe_base_savings_transition",
            ("base_savings_semantically_available",), (), existing_base, static_cap, (transition_provenance,
            BehavioralProvenance("measured_structural", "preserved_base_declaration", "unchanged_exact_declaration",
                _ref("supporting_declaration", preserved[0]))), static=True)
    obligations = tuple(sorted(obligations, key=lambda o: o.obligation_id))
    coverage_map = {o.semantic_dimension: (o.semantic_dimension,) for o in obligations}
    coverage_map.update({"successful_verification_gate": ("authentication_gate", "failed_auth_no_state_change"),
        "verification_lifecycle": ("authentication_gate", "failed_auth_no_state_change"),
        "savings_funding_semantics": ("successful_transfer_conservation", "unsuccessful_debit_no_credit"),
        "savings_credit_guard": ("unsuccessful_debit_no_credit",),
        "savings_interest_semantics": ("savings_interest_target",),
        "candidate_interest_calculation": ("savings_interest_target",),
        "credential_ownership": ("credential_lifecycle",), "credential_persistence": ("credential_lifecycle",),
        "existing_savings_transition": ("base_savings_transition", "savings_interest_target")
            if transition == "subclass_specialization" else ("base_savings_transition",)})
    coverage_map.update({dim: ("credential_lifecycle",) for dim in (
        "credential_source", "credential_verification_mechanism", "exercise_hashing_constraint") if dim in human})
    coverage_rows = []
    for dimension, families in sorted(coverage_map.items()):
        selected = tuple(o for o in obligations if o.semantic_dimension in families)
        mode = "unresolved_observability" if any(o.evidence_mode == "unresolved_observability" for o in selected) else (
            "runtime_required" if any(o.evidence_mode == "runtime_required" for o in selected) else "static_satisfied")
        coverage_rows.append(BehavioralCoverage(dimension, tuple(o.obligation_id for o in selected), mode,
            "observation_evidence_missing" if mode == "unresolved_observability" else mode))
    coverage = tuple(coverage_rows)
    requirements = tuple(BehavioralEvidenceRequirement(o.obligation_id, o.evidence_mode,
        tuple(c.subject for c in o.required_observation_capability)) for o in obligations)
    gap_subjects = sorted({c.subject for o in obligations for c in o.required_observation_capability if not c.available})
    observation_gaps = tuple(BehavioralObservationGap(tuple(o.obligation_id for o in obligations
        if any(c.subject == subject and not c.available for c in o.required_observation_capability)), subject,
        next(c.capability for o in obligations for c in o.required_observation_capability if c.subject == subject and not c.available))
        for subject in gap_subjects)
    harness = tuple(ExecutionHarnessConstraint(tuple(o.obligation_id for o in obligations
        if o.evidence_mode != "static_satisfied" and t in o.target_definitions), (t,)) for t in console_targets)
    status = "behavior_spec_defined_with_observation_gaps" if observation_gaps else "behavior_spec_defined"
    measured["obligation_normalization_seconds"] += perf_counter() - tick
    return _spec(checked, materialized, candidate, scope, plan, transition, obligations, coverage,
        requirements, (), observation_gaps, harness, calculations, status)


def _spec(checked, materialized, candidate, scope, plan, transition, obligations, coverage,
        requirements, oracle_gaps, observation_gaps, harness, calculations, status):
    return BehavioralValidationSpecification(checked.task_fingerprint, checked.effective_design_fingerprint,
        plan.fingerprint, scope.fingerprint, candidate.fingerprint, materialized.fingerprint, checked.fingerprint,
        transition, obligations, coverage, requirements, oracle_gaps, observation_gaps, harness, calculations,
        tuple(sorted({n.proposed_test_file for n in scope.validation_evidence_needs if n.proposed_test_file})), status)


def _payload_gate(payload):
    if type(payload) is dict:
        for key, value in payload.items():
            if key == "authority" and value != "behavioral_oracle_only":
                _fail("behavior_spec_authority_escalation", key)
            if key in AUTHORITY_KEYS and value is not False:
                _fail("behavior_spec_authority_escalation", key)
            if key in FORBIDDEN_PAYLOAD_KEYS:
                _fail("behavior_spec_invalid", "declarative schema rejects executable payloads")
            _payload_gate(value)
    elif type(payload) in {tuple, list}:
        if len(payload) > MAX_ITEMS:
            _fail("behavior_spec_invalid", "collection bound")
        for item in payload:
            _payload_gate(item)


def _run(compile_receipt, materialized, candidate, admitted_scope, inputs, measured):
    checked = _reconstruct(compile_receipt, materialized, candidate, admitted_scope, inputs, measured)
    spec = _project(checked, materialized, candidate, admitted_scope, inputs, measured)
    tick = perf_counter()
    payload = spec.as_dict()
    if len(_json(payload).encode("utf-8")) > MAX_SPEC_BYTES:
        _fail("behavior_spec_invalid", "specification byte bound")
    measured["fingerprint_construction_seconds"] += perf_counter() - tick
    return spec


def project_behavioral_validation_specification(compile_receipt, *, materialized, candidate,
        admitted_scope, timings=None, **fresh_inputs):
    """Deterministic projection; supplied lineage is independently reconstructed."""
    measured = {} if timings is None else timings
    measured.update({key: 0.0 for key in TIMING_FIELDS})
    began = perf_counter()
    try:
        return _run(compile_receipt, materialized, candidate, admitted_scope, fresh_inputs, measured)
    except BehavioralSpecificationError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("behavior_spec_invalid", type(exc).__name__)
    finally:
        measured["total_seconds"] = perf_counter() - began


def validate_behavioral_validation_specification(specification, *, compile_receipt, materialized,
        candidate, admitted_scope, timings=None, **fresh_inputs):
    """Pure closed-schema reconstruction; no trust in UI/session or fingerprints."""
    measured = {} if timings is None else timings
    measured.update({key: 0.0 for key in TIMING_FIELDS})
    began = perf_counter()
    try:
        payload = specification.as_dict() if type(specification) is BehavioralValidationSpecification else specification
        if type(payload) is not dict or len(_json(payload).encode("utf-8")) > MAX_SPEC_BYTES:
            _fail("behavior_spec_invalid", "bounded closed specification required")
        _payload_gate(payload)
        if set(payload) != {f.name for f in fields(BehavioralValidationSpecification)} | {"behavioral_spec_fingerprint"}:
            _fail("behavior_spec_invalid", "closed specification schema required")
        rebuilt = _run(compile_receipt, materialized, candidate, admitted_scope, fresh_inputs, measured)
        if _json(payload) != _json(rebuilt.as_dict()):
            _fail("behavior_spec_stale", "canonical oracle, coverage, lineage or authority differs")
        return rebuilt
    except BehavioralSpecificationError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("behavior_spec_invalid", type(exc).__name__)
    finally:
        measured["total_seconds"] = perf_counter() - began


build_behavioral_validation_specification = project_behavioral_validation_specification
