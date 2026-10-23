"""PATCH.SCOPE.EXPAND.1: evidence-bound structural requirements, never authority.

The frozen DETECT.2 result is a producer receipt, not a request to reinterpret
the answer. This consumer checks its exact input bindings and consumes typed
commitments. It reads no files, discovers no classes, emits no Java and cannot
be consumed as an AuthoringRepairScope. Admission belongs to a later phase.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from time import perf_counter

from core.authoring_repair_scope import AuthoringRepairScope
from core.class_semantic_context import ClassSemanticContext, project_class_semantic_context
from core.design_intent_continuation import EffectiveProposedDesignIntent
from core.oop_intent_detector import AUTH_DIMENSIONS, SAVINGS_DIMENSIONS, OOPIntentDetection
from core.proposed_design_intent import ProposedDesignIntent, project_proposed_design_intent
from core.repair_scope import RepairScope, MAX_REPAIR_MEMBERS
from core.task_contract import TaskContract

PHASE_ID = "PATCH.SCOPE.EXPAND.1"
SCHEMA_VERSION = "patch_scope_expand_1_v1"
MAX_CONTEXTS = 8
MAX_RELATED_CONTEXTS = MAX_CONTEXTS - 1
MAX_EXISTING_TARGETS = 32
MAX_NEW_TARGETS = 32
MAX_CAPABILITIES = 48
MAX_API_REQUIREMENTS = 8
MAX_REASONS = 64
MAX_DEFERRED_ITEMS = 32
MAX_EVIDENCE = 128
MAX_SERIALIZED_BYTES = 65_536
CATEGORIES = frozenset({"MUST_EDIT_EXISTING", "MUST_CREATE_LOGICAL",
    "MAY_REQUIRE_EXISTING_API_CHANGE", "DEFERRED_IMPLEMENTATION_TARGET"})
STATUSES = frozenset({"expansion_required", "semantic_intent_unresolved", "not_applicable",
    "scope_expansion_not_required", "scope_evidence_incomplete", "reacquisition_required",
    "invalid_proposal", "additional_semantic_clarification_required", "bounded"})
BLAST_RADII = ("member", "class", "cross-class", "new-definition", "API-surface")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _bound(items, kind, limit, name):
    if not isinstance(items, tuple) or len(items) > limit or any(not isinstance(x, kind) for x in items):
        raise ValueError(f"{name}_bound_exceeded")


def _label(value):
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("invalid_structural_label")


def _refs(values):
    _bound(values, str, 16, "evidence_refs")
    if not values or any(not _sha(x.rsplit(":", 1)[-1]) for x in values):
        raise ValueError("invalid_structural_evidence_refs")


def detection_fingerprint(detection: OOPIntentDetection) -> str:
    """Bind deterministic receipt content; timings never participate in identity."""
    if not isinstance(detection, OOPIntentDetection):
        raise TypeError("typed_detection_required")
    return _hash({k: v for k, v in detection.as_dict().items() if not k.endswith("_seconds")})


def scope_fingerprint(scope: RepairScope | AuthoringRepairScope | None) -> str:
    """Snapshot existing contracts without invoking their disk-reading renderers."""
    if scope is None:
        return _hash(None)
    if isinstance(scope, AuthoringRepairScope):
        return _hash(asdict(scope))
    if isinstance(scope, RepairScope):
        return _hash(scope.as_dict())
    raise TypeError("typed_current_scope_required")


@dataclass(frozen=True, slots=True)
class ScopeEvidence:
    reference: str
    provenance: str
    binding_fingerprint: str
    fact: str

    def __post_init__(self):
        _label(self.fact)
        _refs((self.reference,))
        if self.provenance not in {"explicit_human", "validated_continuation", "current_source_fact"}:
            raise ValueError("invalid_scope_provenance")
        if not _sha(self.binding_fingerprint):
            raise ValueError("invalid_evidence_binding")


@dataclass(frozen=True, slots=True)
class StructuralCapability:
    code: str
    target: str
    requirement: str
    certainty: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self):
        for x in (self.code, self.target, self.requirement):
            _label(x)
        if self.certainty not in {"MUST_SUPPORT", "NEEDS_TRANSITION_DECISION", "MAY_REQUIRE_EXISTING_API_CHANGE"}:
            raise ValueError("invalid_capability_certainty")
        _refs(self.evidence_refs)


@dataclass(frozen=True, slots=True)
class StructuralTarget:
    target: str
    owner: str
    name: str
    kind: str
    category: str
    reason: str
    evidence_refs: tuple[str, ...]
    parent: str | None = None
    file: str | None = None
    api_surface: bool = False
    declaration_fingerprint: str | None = None
    member_span: tuple[int, int] | None = None

    def __post_init__(self):
        for x in (self.target, self.owner, self.name, self.kind, self.reason):
            _label(x)
        if self.category not in CATEGORIES:
            raise ValueError("invalid_target_category")
        for x in (self.parent, self.file):
            if x is not None:
                _label(x)
        if self.category == "MUST_CREATE_LOGICAL" and self.file is not None:
            raise ValueError("logical_creation_does_not_select_layout")
        if self.declaration_fingerprint is not None and not _sha(self.declaration_fingerprint):
            raise ValueError("invalid_existing_declaration_binding")
        if self.member_span is not None and (not isinstance(self.member_span, tuple)
                or len(self.member_span) != 2 or any(type(x) is not int for x in self.member_span)
                or not 1 <= self.member_span[0] <= self.member_span[1]):
            raise ValueError("invalid_existing_member_span")
        _refs(self.evidence_refs)


@dataclass(frozen=True, slots=True)
class DeferredStructuralDecision:
    target: str
    decision: str
    alternatives: tuple[str, ...] = ()
    semantic_recheck_if_behavior_changes: bool = False

    def __post_init__(self):
        _label(self.target)
        _label(self.decision)
        _bound(self.alternatives, str, 8, "deferred_alternatives")
        for x in self.alternatives:
            _label(x)


@dataclass(frozen=True, slots=True)
class CurrentEditScope:
    status: str
    fingerprint: str
    repair_scope_fingerprint: str
    snapshot_json: str

    def __post_init__(self):
        if self.status not in {"none", "method_local"} or not _sha(self.fingerprint) or not _sha(self.repair_scope_fingerprint):
            raise ValueError("invalid_current_scope_snapshot")
        if len(self.snapshot_json.encode("utf-8")) > MAX_SERIALIZED_BYTES or _json(json.loads(self.snapshot_json)) != self.snapshot_json:
            raise ValueError("invalid_current_scope_snapshot")

    def as_dict(self):
        snapshot = json.loads(self.snapshot_json)
        return {"status": self.status, "fingerprint": self.fingerprint,
            "repair_scope_fingerprint": self.repair_scope_fingerprint,
            "members": [] if snapshot is None else snapshot["members"], "snapshot": snapshot}


@dataclass(frozen=True, slots=True)
class StructuralScopeExpansionProposal:
    task_contract_fingerprint: str
    design_fingerprint: str
    effective_design_fingerprint: str
    detection_fingerprint: str
    repository_id: str
    source_bindings: tuple[tuple[str, str, str, str], ...]
    current_edit_scope: CurrentEditScope
    required_capabilities: tuple[StructuralCapability, ...]
    existing_targets: tuple[StructuralTarget, ...]
    new_logical_targets: tuple[StructuralTarget, ...]
    deferred_decisions: tuple[DeferredStructuralDecision, ...]
    reasons: tuple[str, ...]
    blast_radius: tuple[str, ...]
    evidence: tuple[ScopeEvidence, ...]
    status: str = field(default="expansion_required", init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    scope_authority: str = field(default="proposal_only", init=False)
    authority: str = field(default="proposal_only", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)
    logical_creation_required: bool = field(init=False)
    candidate: None = field(default=None, init=False)
    patch: str = field(default="", init=False)

    def __post_init__(self):
        for value in (self.task_contract_fingerprint, self.design_fingerprint,
                      self.effective_design_fingerprint, self.detection_fingerprint):
            if not _sha(value):
                raise ValueError("invalid_proposal_fingerprint")
        _label(self.repository_id)
        if not isinstance(self.current_edit_scope, CurrentEditScope):
            raise ValueError("typed_scope_snapshot_required")
        _bound(self.source_bindings, tuple, MAX_CONTEXTS, "source_bindings")
        for row in self.source_bindings:
            if len(row) != 4 or not _sha(row[2]) or not _sha(row[3]):
                raise ValueError("invalid_source_binding")
            _label(row[0]); _label(row[1])
        for name, kind, limit in (("required_capabilities", StructuralCapability, MAX_CAPABILITIES),
                ("existing_targets", StructuralTarget, MAX_EXISTING_TARGETS),
                ("new_logical_targets", StructuralTarget, MAX_NEW_TARGETS),
                ("deferred_decisions", DeferredStructuralDecision, MAX_DEFERRED_ITEMS),
                ("reasons", str, MAX_REASONS), ("blast_radius", str, len(BLAST_RADII)),
                ("evidence", ScopeEvidence, MAX_EVIDENCE)):
            _bound(getattr(self, name), kind, limit, name)
        if any(x not in BLAST_RADII for x in self.blast_radius):
            raise ValueError("invalid_blast_radius")
        if any(x.category != "MUST_CREATE_LOGICAL" for x in self.new_logical_targets):
            raise ValueError("invalid_logical_target")
        if sum(x.category == "MAY_REQUIRE_EXISTING_API_CHANGE" for x in self.existing_targets) > MAX_API_REQUIREMENTS:
            raise ValueError("api_requirements_bound_exceeded")
        references = {x.reference for x in self.evidence}
        if any(set(x.evidence_refs) - references for x in (*self.required_capabilities, *self.existing_targets, *self.new_logical_targets)):
            raise ValueError("unbound_target_evidence")
        object.__setattr__(self, "logical_creation_required", bool(self.new_logical_targets))
        if len(self.to_json().encode("utf-8")) > MAX_SERIALIZED_BYTES:
            raise ValueError("serialized_bytes_bound_exceeded")

    def as_dict(self):
        value = asdict(self)
        value["phase_id"] = PHASE_ID
        value["current_edit_scope"] = self.current_edit_scope.as_dict()
        return json.loads(_json(value))

    def to_json(self):
        return _json(self.as_dict())

    @property
    def fingerprint(self):
        return sha256(self.to_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class StructuralScopeExpansionResult:
    status: str
    proposal: StructuralScopeExpansionProposal | None = None
    reasons: tuple[str, ...] = ()
    evidence_needs: tuple[str, ...] = ()
    semantic_status: str = "unresolved"
    candidate: None = field(default=None, init=False)
    patch: str = field(default="", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)
    scope_authority: str = field(default="proposal_only", init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)

    def __post_init__(self):
        if self.status not in STATUSES or (self.status == "expansion_required") != isinstance(self.proposal, StructuralScopeExpansionProposal):
            raise ValueError("invalid_expansion_result")
        _bound(self.reasons, str, MAX_REASONS, "result_reasons")
        _bound(self.evidence_needs, str, MAX_CONTEXTS, "evidence_needs")

    @property
    def first_remaining_blocker(self):
        return "SCOPE_EXPANSION_REQUIRED" if self.status == "expansion_required" else self.status.upper()

    def as_dict(self):
        value = asdict(self)
        value.update(phase_id=PHASE_ID, first_remaining_blocker=self.first_remaining_blocker,
            proposal=None if self.proposal is None else self.proposal.as_dict())
        return json.loads(_json(value))


class ScopeExpansionError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _validate_context(context, raw, repository_id):
    if not isinstance(context, ClassSemanticContext) or context.status != "complete" or context.overflow:
        raise ScopeExpansionError("scope_evidence_incomplete")
    if not isinstance(raw, bytes) or sha256(raw).hexdigest() != context.source_fingerprint:
        raise ScopeExpansionError("reacquisition_required")
    if context.repository_id != repository_id or not context.class_identity or not context.target or not context.read_only:
        raise ScopeExpansionError("source_binding_mismatch")
    target = context.target
    projected = project_class_semantic_context(raw=raw, language=context.language, file=context.file,
        target={"kind": target.kind, "name": target.name, "start": target.span.start, "end": target.span.end,
                "content": raw[target.span.start:target.span.end].decode("utf-8")},
        expected_source_fingerprint=context.source_fingerprint, repository_id=repository_id)
    if context != projected:
        raise ScopeExpansionError("source_context_mismatch")


def _validate_semantics(contract, design, detection, context, repository_id):
    if not isinstance(contract, TaskContract) or not isinstance(design, (ProposedDesignIntent, EffectiveProposedDesignIntent)) or not isinstance(detection, OOPIntentDetection):
        raise ScopeExpansionError("typed_frozen_inputs_required")
    base = design.base if isinstance(design, EffectiveProposedDesignIntent) else design
    if base != project_proposed_design_intent(contract) or not contract.routing_allowed or not contract.preservation.passed:
        raise ScopeExpansionError("design_binding_mismatch")
    if (detection.task_contract_fingerprint != _hash(contract.as_dict()) or detection.design_fingerprint != design.fingerprint
            or detection.repository_id != repository_id or detection.source_path != context.file
            or detection.source_fingerprint != context.source_fingerprint
            or detection.class_identity != context.class_identity.qualified_name):
        raise ScopeExpansionError("semantic_detection_binding_mismatch")
    if isinstance(design, EffectiveProposedDesignIntent):
        c = design.continuation
        if (c.task_contract_fingerprint != base.task_contract_fingerprint or c.repository_id != repository_id
                or c.source_path != context.file or c.source_fingerprint != context.source_fingerprint
                or c.class_identity != context.class_identity.qualified_name):
            raise ScopeExpansionError("effective_design_binding_mismatch")
        dimensions = {x.dimension for x in c.typed_answer_commitments
                      if x.dimension in AUTH_DIMENSIONS | SAVINGS_DIMENSIONS}
        if (set(c.resolved_dimensions) != dimensions or set(c.remaining_dimensions) & dimensions
                or any(x.answer_fingerprint != c.answer_fingerprint for x in c.typed_answer_commitments)):
            raise ScopeExpansionError("effective_design_partition_mismatch")
    if detection.status == "no_gap":
        if (design.status != "resolved" or detection.possible_intent_gaps
                or any(x.disposition == "human_owned_material" for x in detection.assessments)
                or {x.dimension for x in detection.assessments} != {x.dimension for x in design.unresolved_dimensions}
                or any(x.dimension in AUTH_DIMENSIONS | SAVINGS_DIMENSIONS
                       and x.disposition != "irrelevant_to_current_transition"
                       and x.reason != "exact_current_authentication_signature_resolves_this_dimension"
                       for x in detection.assessments)):
            raise ScopeExpansionError("invalid_semantic_ready_receipt")
    return base


def _snapshot_scope(scope, expected, contexts):
    fingerprint = scope_fingerprint(scope)
    if scope is None:
        if expected is not None and expected != fingerprint:
            raise ScopeExpansionError("current_scope_fingerprint_mismatch")
        return CurrentEditScope("none", fingerprint, fingerprint, "null")
    if expected != fingerprint:
        raise ScopeExpansionError("current_scope_fingerprint_mismatch")
    measured = scope.measured if isinstance(scope, AuthoringRepairScope) else scope
    if not measured.is_complete or not isinstance(measured.members, tuple) or not 1 <= len(measured.members) <= MAX_REPAIR_MEMBERS:
        raise ScopeExpansionError("current_scope_incomplete")
    if not all(_sha(x) for x in (measured.source_fingerprint, measured.evidence_fingerprint, measured.control_fingerprint)):
        raise ScopeExpansionError("current_scope_binding_mismatch")
    by_file = {c.file: (c, raw) for c, raw in contexts}
    if measured.primary_file not in by_file or measured.repository_id != contexts[0][0].repository_id:
        raise ScopeExpansionError("current_scope_binding_mismatch")
    if measured.source_fingerprint != sha256(by_file[measured.primary_file][1]).hexdigest():
        raise ScopeExpansionError("reacquisition_required")
    ordered_ranges = []
    for m in measured.members:
        if m.file != measured.primary_file or not m.diagnostics:
            raise ScopeExpansionError("current_scope_member_mismatch")
        matches = [(c, raw, method) for c, raw in contexts if c.file == m.file
            for method in (*c.methods, *c.explicit_constructors)
            if method.name == m.symbol and m.kind == "function"
            and method.span.start_line == m.start_line and method.span.end_line == m.end_line
            and raw[method.span.start:method.span.end].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n") == m.source_snippet]
        if len(matches) != 1 or any(d.file != m.file or d.severity != "error" or d.kind != "compiler_error"
                or not m.start_line <= d.line <= m.end_line for d in m.diagnostics):
            raise ScopeExpansionError("current_scope_member_mismatch")
        c, raw, method = matches[0]
        normalized = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        start = len(raw[:method.span.start].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"))
        ordered_ranges.append((start, start + len(m.source_snippet)))
    if not any(m.symbol == measured.primary_symbol for m in measured.members) or any(a[1] > b[0] for a, b in zip(ordered_ranges, ordered_ranges[1:])):
        raise ScopeExpansionError("current_scope_member_mismatch")
    if isinstance(scope, AuthoringRepairScope):
        preflight = json.loads(scope.preflight_json)
        if (tuple(ordered_ranges) != scope.member_ranges or scope.source != normalized or scope.language != c.language
                or len(scope.member_bindings) != len(measured.members)
                or preflight.get("receipt_fingerprint") != measured.evidence_fingerprint
                or preflight.get("control_sha256") != measured.control_fingerprint
                or preflight.get("repository_id") != measured.repository_id):
            raise ScopeExpansionError("authoring_scope_binding_mismatch")
        for m, binding in zip(measured.members, scope.member_bindings):
            if binding is not None and not binding.is_current_for(authoritative_source=scope.source,
                    source_path=m.file, target_symbol=m.symbol, target_snippet=m.source_snippet):
                raise ScopeExpansionError("authoring_scope_binding_mismatch")
    return CurrentEditScope("method_local", fingerprint, scope_fingerprint(measured), _json(measured.as_dict()))


def _method_tree(raw, method):
    from tree_sitter_language_pack import get_parser
    root = get_parser("java").parse(raw).root_node
    stack = [root]
    while stack:
        node = stack.pop()
        if node.start_byte == method.span.start and node.end_byte == method.span.end and node.type == "method_declaration":
            return node
        stack.extend(reversed(node.named_children))
    return None


def _debit_suitability(context, raw, method, balance):
    """Closed syntax proof; neither a method name nor boolean return is proof.

    Recognize an unconditional, sole debit with normal completion, or an exact
    balance guard/debit/true followed by false. Everything else is unknown.
    Package access needs later layout evidence; public/protected works anywhere.
    """
    if method.visibility not in {"public", "protected"} or method.ownership != "instance" or len(method.parameters) != 1:
        return "not_established", "subclass_visibility_or_debit_contract_not_established"
    parameter = method.parameters[0]
    if parameter.name == balance.name or parameter.declared_type != balance.declared_type:
        return "not_established", "debit_parameter_contract_not_established"
    node = _method_tree(raw, method)
    body = node.child_by_field_name("body") if node else None
    statements = body.named_children if body else []

    def text(n):
        return raw[n.start_byte:n.end_byte].decode("utf-8") if n else ""

    def field(n):
        return n is not None and (n.type == "identifier" and text(n) == balance.name or
            n.type == "field_access" and text(n.child_by_field_name("object")) == "this"
            and text(n.child_by_field_name("field")) == balance.name)

    def debit(statement):
        if statement.type != "expression_statement" or len(statement.named_children) != 1:
            return False
        expression = statement.named_children[0]
        return (expression.type == "assignment_expression" and field(expression.child_by_field_name("left"))
            and text(expression.child_by_field_name("operator")) == "-="
            and text(expression.child_by_field_name("right")) == parameter.name)

    def returns(statement, value):
        return statement.type == "return_statement" and len(statement.named_children) == 1 and text(statement.named_children[0]) == value

    if len(statements) == 1 and debit(statements[0]) and method.return_type == "void":
        return "sufficient", "unconditional_debit_has_no_silent_failure_path"
    if len(statements) == 2 and statements[0].type == "if_statement" and returns(statements[1], "false") and method.return_type == "boolean":
        condition = statements[0].child_by_field_name("condition")
        if condition and condition.type == "parenthesized_expression" and len(condition.named_children) == 1:
            condition = condition.named_children[0]
        consequence = statements[0].child_by_field_name("consequence")
        parts = consequence.named_children if consequence and consequence.type == "block" else []
        if (condition and condition.type == "binary_expression" and field(condition.child_by_field_name("left"))
                and text(condition.child_by_field_name("operator")) == ">="
                and text(condition.child_by_field_name("right")) == parameter.name
                and statements[0].child_by_field_name("alternative") is None
                and len(parts) == 2 and debit(parts[0]) and returns(parts[1], "true")):
            return "sufficient", "conditional_debit_exposes_exact_success_result"
    if method.return_type == "void":
        return "not_established", "conditional_or_unproven_void_debit_exposes_no_success_result"
    return "not_established", "return_value_alone_does_not_prove_successful_transfer"


def _construct_structural_scope_expansion(*, task_contract, design_intent, semantic_detection,
        current_context, current_source, repository_id, current_scope=None,
        expected_scope_fingerprint=None, related_contexts=(), timings=None,
        _transition_value=None, _transition_continuation_fingerprint=None,
        _refreshed_effective_design_fingerprint=None):
    """Compare only acquired buffers and frozen intent. Never admit an expansion.

    ``expected_scope_fingerprint`` is the independently retained current scope
    identity; a scope cannot vouch for its own replacement. DETECT.2 owns answer
    validation upstream. Related contexts must already be acquired, with bytes.
    """
    started = perf_counter()
    if _transition_value is not None and (
            _transition_value not in {"savings_only_on_subclass", "preserve_base_compatibility", "subclass_specialization"}
            or not _sha(_transition_continuation_fingerprint)
            or not _sha(_refreshed_effective_design_fingerprint)):
        return StructuralScopeExpansionResult("invalid_proposal", reasons=("invalid_validated_transition_adapter",))
    if _transition_value is None and any(x is not None for x in (
            _transition_continuation_fingerprint, _refreshed_effective_design_fingerprint)):
        return StructuralScopeExpansionResult("invalid_proposal", reasons=("incomplete_validated_transition_adapter",))
    durations = dict(semantic_ready_validation_seconds=0.0, structural_comparison_seconds=0.0,
        expansion_classification_seconds=0.0, proposal_serialization_seconds=0.0)

    def finish(status, *, reasons=(), needs=(), proposal=None, ready=False):
        if timings is not None:
            timings.update(durations, total_seconds=perf_counter() - started)
        return StructuralScopeExpansionResult(status, proposal, reasons, needs,
            semantic_status="ready" if ready else "unresolved")

    try:
        _bound(related_contexts, tuple, MAX_CONTEXTS - 1, "related_contexts")
        contexts = ((current_context, current_source), *related_contexts)
        for row in contexts:
            if len(row) != 2:
                raise ScopeExpansionError("typed_source_pair_required")
            _validate_context(*row, repository_id)
        if len({c.class_identity.qualified_name for c, _ in contexts}) != len(contexts):
            raise ScopeExpansionError("ambiguous_acquired_class")
        if len({c.class_identity.name for c, _ in contexts}) != len(contexts):
            raise ScopeExpansionError("scope_evidence_incomplete")
        versions = {}
        for c, _ in contexts:
            if c.file in versions and versions[c.file] != c.source_fingerprint:
                raise ScopeExpansionError("inconsistent_acquired_source_versions")
            versions[c.file] = c.source_fingerprint
        base = _validate_semantics(task_contract, design_intent, semantic_detection, current_context, repository_id)
        snapshot = _snapshot_scope(current_scope, expected_scope_fingerprint, contexts)
        durations["semantic_ready_validation_seconds"] = perf_counter() - started
        # Review-only orders do not request future implementation authority.
        if task_contract.task.type in {"review", "analysis", "comparative_analysis", "question", "research"}:
            return finish("not_applicable", reasons=("no_future_structural_implementation_request",))
        if semantic_detection.status == "not_applicable":
            return finish("not_applicable", reasons=("no_future_design_commitment",))
        if semantic_detection.status == "stale_source":
            return finish("reacquisition_required", reasons=("semantic_detection_source_stale",))
        if semantic_detection.status in {"projection_mismatch", "provenance_rejected", "repository_mismatch"}:
            return finish("invalid_proposal", reasons=("semantic_detection_binding_rejected",))
        if semantic_detection.status != "no_gap":
            return finish("semantic_intent_unresolved", reasons=("semantic_ready_detection_required",))

        tick = perf_counter()
        by_class = {c.class_identity.name: (c, raw) for c, raw in contexts}
        evidence, capabilities, existing, new, deferred, needs = [], [], [], [], [], []

        def fact(provenance, value, binding, description):
            reference = provenance + ":" + _hash(value)
            item = ScopeEvidence(reference, provenance, binding, description)
            if item not in evidence:
                evidence.append(item)
            return reference

        def human(item):
            return fact("explicit_human", item.as_dict(), base.fingerprint, item.evidence.source_text)

        def source(c):
            return fact("current_source_fact", c.as_dict(), c.source_fingerprint,
                "exact acquired structure of " + c.class_identity.qualified_name)

        def capability(code, target, requirement, refs, certainty="MUST_SUPPORT"):
            item = StructuralCapability(code, target, requirement, certainty, tuple(dict.fromkeys(refs)))
            if item not in capabilities:
                capabilities.append(item)

        def target(owner, name, kind, category, reason, refs, parent=None, api=False, member=None):
            declaration_fp, member_span = None, None
            if member is not None:
                raw = by_class[owner][1]
                snippet = raw[member.span.start:member.span.end].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                declaration_fp = sha256(snippet.encode("utf-8")).hexdigest()
                member_span = (member.span.start_line, member.span.end_line)
            item = StructuralTarget(owner if kind == "new_class" else owner + "::" + name,
                owner, name, kind, category, reason, tuple(dict.fromkeys(refs)), parent,
                None if category == "MUST_CREATE_LOGICAL" else by_class[owner][0].file, api,
                declaration_fp, member_span)
            collection = new if category == "MUST_CREATE_LOGICAL" else existing
            if item not in collection:
                collection.append(item)

        def defer(owner, decision, alternatives=(), semantic=False):
            item = DeferredStructuralDecision(owner, decision, alternatives, semantic)
            if item not in deferred:
                deferred.append(item)

        declared_names = set(by_class)
        # These are names in supplied buffers, not a repository-wide inventory.
        from core.treesitter_parse import structural_definitions
        for c, raw in contexts:
            definitions = structural_definitions(raw.decode("utf-8"), c.language)
            declared_names.update(d["name"] for d in definitions["definitions"] if d["kind"] == "class")

        for rel in design_intent.relationships:
            refs = [human(rel)]
            if rel.parent not in by_class:
                needs.append(rel.parent)
                continue
            parent, _ = by_class[rel.parent]
            refs.append(source(parent))
            if parent.class_identity.is_final:
                capability("base_inheritability", rel.parent,
                    "the committed subtype requires a base declaration that permits inheritance", refs)
                target(rel.parent, "inheritability", "class_declaration", "MUST_EDIT_EXISTING",
                    "exact_final_base_declaration_prevents_explicit_inheritance", refs, api=True)
            if rel.child not in by_class:
                if rel.child in declared_names:
                    needs.append(rel.child)
                    continue
                capability("new_subtype_definition", rel.child,
                    "logical subtype with required parent; absence is limited to acquired source", refs)
                target(rel.child, rel.child, "new_class", "MUST_CREATE_LOGICAL", "explicit_inheritance_requires_missing_logical_definition", refs, rel.parent)
                defer(rel.child, "source_layout", ("repository_convention_evidence_needed",))
            elif by_class[rel.child][0].class_identity.extends != rel.parent:
                refs.append(source(by_class[rel.child][0]))
                target(rel.child, "inheritance", "inheritance", "MUST_EDIT_EXISTING", "explicit_parent_differs_from_current_declaration", refs, rel.parent)
            if parent.explicit_constructors:
                capability("subclass_initialization", rel.child,
                    "initialization path must compatibly initialize the explicit base constructor via super construction", refs)
                defer(rel.child, "constructor_signature_and_initialization_details")
                if all(c.visibility == "private" for c in parent.explicit_constructors):
                    target(rel.parent, "subclass_initialization_capability", "capability",
                        "MAY_REQUIRE_EXISTING_API_CHANGE", "only_private_base_constructors_leave_subclass_construction_path_unestablished",
                        refs, api=True)
                    defer(rel.parent, "base_constructor_access_path_and_layout_evidence")

        new_classes = {x.owner for x in new if x.kind == "new_class"}
        for state in design_intent.state_commitments:
            refs = [human(state)]
            if state.owner not in by_class and state.owner not in new_classes:
                needs.append(state.owner)
                continue
            capability("subclass_owned_state", state.owner + "::" + state.state,
                "required state belongs exclusively to the explicit owner", refs)
            owned = by_class.get(state.owner)
            if owned is None or not any(f.name == state.state for f in owned[0].fields):
                target(state.owner, state.state, "new_field_required", "MUST_CREATE_LOGICAL", "exclusive_state_missing_from_desired_owner", refs)
                defer(state.owner + "::" + state.state, "state_type_visibility_and_initial_value")
            if state.base_exclusion in by_class:
                c, _ = by_class[state.base_exclusion]
                for f in c.fields:
                    if f.name == state.state:
                        target(c.class_identity.name, f.name, "existing_field", "MUST_EDIT_EXISTING", "explicit_subclass_only_state_excludes_base_ownership", (*refs, source(c)))

        commitments = (design_intent.continuation.typed_answer_commitments
            if isinstance(design_intent, EffectiveProposedDesignIntent) else ())
        values = {x.dimension: x.value for x in commitments}
        answer_refs = {x.dimension: fact("validated_continuation", x.as_dict(),
            design_intent.continuation.fingerprint, x.evidence.source_text) for x in commitments}
        if _transition_value is not None:
            values["existing_savings_transition"] = _transition_value
            answer_refs["existing_savings_transition"] = fact(
                "validated_continuation",
                {"dimension": "existing_savings_transition", "value": _transition_value},
                _transition_continuation_fingerprint,
                "validated human-owned existing savings transition: " + _transition_value)
        savings_states = [s for s in design_intent.state_commitments if s.state_role == "savings_state"]
        for gate in design_intent.behavior_gates:
            credential_owner = values.get("credential_ownership") or (savings_states[0].owner if savings_states else current_context.class_identity.name)
            owner = credential_owner
            explicit_method = gate.gated_behavior.isidentifier()
            method = gate.gated_behavior if explicit_method else "authentication_gated_savings_capability"
            # A qualified identifier already present in a typed BehaviorGate is
            # a member commitment. This is not extraction from raw task prose.
            parts = gate.gated_behavior.split("::")
            if len(parts) == 2 and all(x.isidentifier() for x in parts):
                owner, method = parts
                explicit_method = True
            if owner not in by_class and owner not in new_classes:
                needs.append(owner)
                continue
            refs = [human(gate), *[answer_refs[k] for k in ("credential_ownership", "credential_source",
                "credential_persistence", "credential_verification_mechanism", "verification_lifecycle") if k in answer_refs]]
            capability("credential_state", credential_owner, "credential-bearing verification capability owned by the specified class; in-memory password when committed", refs)
            capability("authentication_gated_savings_operation", owner,
                "verification boundary gates each requested savings operation when operation_gated is committed", refs)
            # Only an exact identifier in the typed gate names an API. Natural
            # language descriptions remain capabilities, never invented names.
            c = by_class.get(owner)
            matches = [] if c is None else [m for m in c[0].methods if m.name == method]
            if matches:
                for m in matches:
                    target(owner, method, "existing_method", "MUST_EDIT_EXISTING", "explicit_verification_boundary_required",
                        (*refs, source(c[0])), member=m)
            else:
                target(owner, method, "new_method_required" if explicit_method else "capability", "MUST_CREATE_LOGICAL", "missing_authentication_gated_capability", refs)
            if credential_owner in new_classes:
                target(credential_owner, "credential_state_and_verification", "capability", "MUST_CREATE_LOGICAL", "owner_requires_credential_bearing_capability", refs)
            defer(credential_owner, "credential_field_method_decomposition_and_verification_API")

        for state in savings_states:
            rel = next((r for r in design_intent.relationships if r.child == state.owner), None)
            if values.get("savings_funding_semantics") == "transfer_from_inherited_balance":
                refs = (human(state), answer_refs["savings_funding_semantics"])
                capability("savings_funding_transition", state.owner,
                    "credit savings state only with money successfully debited from inherited account state", refs)
                if rel is None or rel.parent not in by_class:
                    needs.append(rel.parent if rel else state.owner + " inherited account context")
                    continue
                parent, raw = by_class[rel.parent]
                fields = [f for f in parent.fields if f.name == "balance" and f.ownership == "instance"]
                if len(fields) != 1:
                    needs.append(rel.parent + " exact balance-debit evidence")
                    continue
                balance = fields[0]
                capability("base_balance_debit", rel.parent,
                    "subclass needs a justified successful debit of inherited balance; private state cannot be directly accessed", (*refs, source(parent)))
                debit_methods = [m for m in parent.methods if any(r.method_span == m.span and r.field_name == balance.name
                    and r.access in {"write", "read_write"} for r in parent.relations)]
                proof = [(m, *_debit_suitability(parent, raw, m, balance)) for m in debit_methods]
                sufficient = any(status == "sufficient" for _, status, _ in proof)
                for m, status, reason in proof:
                    if m.name == "withdraw" or status == "sufficient":
                        fact("current_source_fact", {"context": parent.as_dict(), "method": asdict(m), "suitability": status, "reason": reason},
                            parent.source_fingerprint, f"{rel.parent}::{m.name}: {status}; {reason}; return={m.return_type}; visibility={m.visibility}")
                # A mutable, subclass-visible field is an existing capability;
                # planning may preserve encapsulation using another mechanism.
                direct = balance.visibility in {"public", "protected"} and not balance.is_final
                if not sufficient and not direct:
                    target(rel.parent, "successful_balance_debit_capability", "capability", "MAY_REQUIRE_EXISTING_API_CHANGE",
                        "private_or_inaccessible_balance_and_no_proven_subclass_visible_successful_debit", (*refs, source(parent)), api=True)
                    defer(rel.parent, "base_debit_API_signature_and_encapsulation_strategy")
            if values.get("savings_interest_semantics") == "interest_applies_to_saving_balance":
                refs = (human(state), answer_refs["savings_interest_semantics"])
                capability("savings_interest_behavior", state.owner + "::" + state.state,
                    "interest applies only to the subclass savings state", refs)
                if state.owner in new_classes:
                    target(state.owner, "savings_interest_behavior", "capability", "MUST_CREATE_LOGICAL", "subclass_savings_interest_capability_required", refs)
                if rel and rel.parent in by_class:
                    parent, _ = by_class[rel.parent]
                    for m in parent.methods:
                        if m.name != "saving":
                            continue
                        writes_balance = any(r.method_span == m.span and r.field_name == "balance" and r.access in {"write", "read_write"} for r in parent.relations)
                        if not writes_balance:
                            continue
                        transition_refs = (*refs, source(parent))
                        transition = values.get("existing_savings_transition")
                        if transition is None:
                            # Frozen EXPAND.1 behavior: the material transition is unresolved.
                            capability("existing_savings_transition", rel.parent + "::saving",
                                "base savings currently mutates base balance; desired subclass savings operates on subclass state", transition_refs, "NEEDS_TRANSITION_DECISION")
                            if m.is_final and m.visibility != "private":
                                target(rel.parent, "savings_transition_capability", "capability", "MAY_REQUIRE_EXISTING_API_CHANGE",
                                    "final_base_savings_requires_compatibility_preserving_transition_capability", transition_refs, api=True)
                                defer(rel.parent + "::saving", "compatible_final_savings_transition_mechanism")
                            target(rel.parent, "saving", "existing_method", "DEFERRED_IMPLEMENTATION_TARGET",
                                "existing_base_savings_ownership_transition_requires_later_decision", transition_refs,
                                api=m.visibility in {"public", "protected"}, member=m)
                            defer(rel.parent + "::saving", "existing_savings_transition", ("retirement", "override", "relocation", "compatibility_preservation"), True)
                        else:
                            resolved_refs = (*transition_refs, answer_refs["existing_savings_transition"])
                            if transition == "savings_only_on_subclass":
                                capability("existing_savings_transition", rel.parent + "::saving",
                                    "base saving behavior must leave the intended base API while subclass savings remains distinct",
                                    resolved_refs, "MUST_SUPPORT")
                                target(rel.parent, "saving", "existing_method", "MAY_REQUIRE_EXISTING_API_CHANGE",
                                    "base_savings_behavior_must_leave_intended_api", resolved_refs,
                                    api=m.visibility in {"public", "protected"}, member=m)
                                defer(rel.parent + "::saving", "base_savings_retirement_or_compatibility_migration",
                                    ("removal", "deprecation", "compatibility_migration"))
                            elif transition == "preserve_base_compatibility":
                                capability("existing_savings_transition", rel.parent + "::saving",
                                    "current BankAccount saving behavior remains semantically required for compatibility",
                                    resolved_refs, "MUST_SUPPORT")
                                target(rel.parent, "saving", "existing_method", "DEFERRED_IMPLEMENTATION_TARGET",
                                    "legacy_base_savings_behavior_is_semantically_preserved", resolved_refs,
                                    api=m.visibility in {"public", "protected"}, member=m)
                                defer(rel.parent + "::saving", "implementation_details_for_preserved_base_savings")
                            else:  # subclass_specialization
                                capability("existing_savings_transition", rel.parent + "::saving",
                                    "base savings contract remains available and supports subclass-specific savings behavior",
                                    resolved_refs, "MUST_SUPPORT")
                                target(rel.parent, "saving", "existing_method", "DEFERRED_IMPLEMENTATION_TARGET",
                                    "base_savings_contract_supports_subclass_specialization", resolved_refs,
                                    api=m.visibility in {"public", "protected"}, member=m)
                                defer(rel.parent + "::saving", "specialization_contract_implementation_details")
                                if m.is_final or m.visibility == "private":
                                    capability("existing_savings_specialization_api", rel.parent + "::saving",
                                        "the exact current declaration prevents subclass specialization without an API transition",
                                        resolved_refs, "MAY_REQUIRE_EXISTING_API_CHANGE")
                                    target(rel.parent, "savings_specialization_capability", "capability",
                                        "MAY_REQUIRE_EXISTING_API_CHANGE",
                                        "final_or_private_base_saving_prevents_subclass_specialization",
                                        resolved_refs, api=True)
                                    defer(rel.parent + "::saving", "compatible_specialization_API_transition")

        durations["structural_comparison_seconds"] = perf_counter() - tick
        if needs:
            unique = tuple(sorted(set(needs)))
            if len(unique) > MAX_CONTEXTS:
                return finish("bounded", reasons=("evidence_needs_bound_exceeded",), ready=True)
            return finish("scope_evidence_incomplete", needs=unique, reasons=("required_related_context_not_acquired",), ready=True)
        tick = perf_counter()
        authorized = set() if current_scope is None else {(m.file, m.symbol, (m.start_line, m.end_line),
            sha256(m.source_snippet.encode("utf-8")).hexdigest()) for m in
            (current_scope.measured if isinstance(current_scope, AuthoringRepairScope) else current_scope).members}
        expansion = bool(new or any(t.category != "MUST_EDIT_EXISTING"
            or (t.file, t.name, t.member_span, t.declaration_fingerprint) not in authorized for t in existing))
        durations["expansion_classification_seconds"] = perf_counter() - tick
        if not expansion:
            return finish("scope_expansion_not_required", reasons=("requirements_fit_current_exact_members",), ready=True)
        radii = set()
        if new:
            radii.add("new-definition")
        owners = {t.owner for t in (*existing, *new)}
        radii.add("cross-class" if len(owners) > 1 else "class")
        if any(t.api_surface for t in existing):
            radii.add("API-surface")
        if any(t.kind in {"existing_method", "existing_field"} for t in existing):
            radii.add("member")
        tick = perf_counter()
        proposal = StructuralScopeExpansionProposal(
            task_contract_fingerprint=_hash(task_contract.as_dict()), design_fingerprint=base.fingerprint,
            effective_design_fingerprint=_refreshed_effective_design_fingerprint or design_intent.fingerprint,
            detection_fingerprint=detection_fingerprint(semantic_detection), repository_id=repository_id,
            source_bindings=tuple(sorted((c.file, c.class_identity.qualified_name, c.source_fingerprint, _hash(c.as_dict())) for c, _ in contexts)),
            current_edit_scope=snapshot, required_capabilities=tuple(capabilities), existing_targets=tuple(existing),
            new_logical_targets=tuple(new), deferred_decisions=tuple(deferred),
            reasons=tuple(sorted({t.reason for t in (*existing, *new)})),
            blast_radius=tuple(x for x in BLAST_RADII if x in radii), evidence=tuple(evidence))
        proposal.to_json()
        durations["proposal_serialization_seconds"] = perf_counter() - tick
        return finish("expansion_required", proposal=proposal, ready=True,
            reasons=("requested_behavior_requires_structure_outside_current_authorized_targets",))
    except ScopeExpansionError as exc:
        durations["semantic_ready_validation_seconds"] = perf_counter() - started
        status = exc.reason if exc.reason in {"reacquisition_required", "scope_evidence_incomplete"} else "invalid_proposal"
        return finish(status, reasons=(exc.reason,))
    except (ValueError, TypeError, UnicodeError, KeyError, AttributeError) as exc:
        reason = str(exc)
        status = "bounded" if "bound_exceeded" in reason else "invalid_proposal"
        return finish(status, reasons=(reason[:512] or "invalid_frozen_input",))


def propose_structural_scope_expansion(*, task_contract, design_intent, semantic_detection,
        current_context, current_source, repository_id, current_scope=None,
        expected_scope_fingerprint=None, related_contexts=(), timings=None):
    """Frozen EXPAND.1 entry point; refresh semantics use a separate adapter."""
    return _construct_structural_scope_expansion(
        task_contract=task_contract, design_intent=design_intent,
        semantic_detection=semantic_detection, current_context=current_context,
        current_source=current_source, repository_id=repository_id,
        current_scope=current_scope, expected_scope_fingerprint=expected_scope_fingerprint,
        related_contexts=related_contexts, timings=timings)


def validate_structural_scope_expansion_proposal(proposal, **current_inputs):
    """Rebuild against fresh supplied inputs; hashes are identities, not admission."""
    if not isinstance(proposal, StructuralScopeExpansionProposal):
        raise ScopeExpansionError("typed_proposal_required")
    current = propose_structural_scope_expansion(**current_inputs)
    if current.proposal is None or current.proposal.to_json() != proposal.to_json():
        raise ScopeExpansionError("stale_or_invalid_proposal")
