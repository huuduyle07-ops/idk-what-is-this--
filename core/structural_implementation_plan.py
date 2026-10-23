"""PATCH.SCOPE.PLAN.1: one planner proposal, no admission or authoring envelope.

The planner chooses code shape. This pure harness consumes already acquired
buffers, reconstructs APPROVE.1 from independent human evidence, and checks a
closed, bounded proposal. Physical paths are suggestions for later ADMIT.1.
No function in this module reads files, executes validation, or calls an author.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from hashlib import sha256
import json
import math
from pathlib import PurePosixPath, PureWindowsPath
import re
from time import perf_counter
from typing import Protocol

from core.structural_scope_approval import validate_structural_scope_approval_receipt
from core.structural_scope_expansion import _debit_suitability

PHASE_ID = "PATCH.SCOPE.PLAN.1"
SCHEMA_VERSION = "patch_scope_plan_1_v1"
MAX_OUTPUT_BYTES = 65_536
MAX_CONTEXT_BYTES = 96_000
MAX_ITEMS = 64
TIMING_FIELDS = ("approval_validation_seconds", "context_projection_seconds",
    "planner_call_seconds", "plan_normalization_seconds", "ceiling_containment_seconds",
    "semantic_validation_seconds", "plan_minimality_seconds", "total_deterministic_seconds")
BOUNDARY = ("This is design planning only. Return the typed proposal vocabulary. "
    "Do not emit code or a patch. Do not claim permission to edit. Do not introduce "
    "infrastructure outside the approved ceiling. Proposed paths confer no authority. "
    "Report new material semantic questions instead of choosing their answers. "
    "Choose unique local definition_id labels and reference those exact labels in "
    "capability coverage. Copy approved target identities from the supplied inventory.")
AREAS = frozenset({"source_layout", "constructor", "state", "credential", "debit",
    "savings_funding", "savings_interest", "existing_saving_transition", "helper_decomposition"})
KINDS = frozenset({"class", "constructor", "field", "method"})
PATCH_PATTERN = re.compile(r"```|(?m:^\s*(?:diff --git |@@ |--- |\+\+\+ ))|[{};]")
DRIFT_PATTERN = re.compile(r"\b(?:lockout|retry[ _-]*limits?|password[ _-]*attempts?|"
    r"overdraft|fees?|interest[ _-]*timing|database|csv|hashing[ _-]*service|"
    r"authentication[ _-]*server|sessions?|file[ _-]*persistence)\b", re.I)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


class PlanError(ValueError):
    def __init__(self, code, reason=""):
        self.code = code
        self.reason = reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise PlanError(code, reason)


def _tuple(value, kind, name):
    if type(value) is not tuple or len(value) > MAX_ITEMS or any(type(x) is not kind for x in value):
        _fail("plan_invalid_output", name)


def _text(value, *, empty=False):
    if (type(value) is not str or len(value) > 1200 or (not value and not empty)
            or any(ord(c) < 32 and c not in "\n\t" for c in value)):
        _fail("plan_invalid_output", "bounded text required")


def _identifier(value):
    _text(value)
    if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", value):
        _fail("plan_invalid_output", "exact Java identifier required")


def _timed(timings, key, tick):
    timings[key] += perf_counter() - tick


def _timings(value):
    result = {} if value is None else value
    result.update({key: 0.0 for key in TIMING_FIELDS})
    return result


@dataclass(frozen=True, slots=True)
class PlanTargetIdentity:
    """Exact typed ceiling identity, including its immutable evidence binding."""
    target: str
    owner: str
    name: str
    kind: str
    category: str
    parent: str | None
    file: str | None
    evidence_refs: tuple[str, ...]
    declaration_fingerprint: str | None
    member_span: tuple[int, ...] | None
    ceiling_target_fingerprint: str

    def __post_init__(self):
        for value in (self.target, self.owner, self.name, self.kind, self.category, self.ceiling_target_fingerprint):
            _text(value)
        _tuple(self.evidence_refs, str, "target evidence")
        for value in (self.parent, self.file, self.declaration_fingerprint):
            if value is not None:
                _text(value)
        if self.member_span is not None:
            _span(self.member_span)

    @classmethod
    def of(cls, target):
        return cls(**{f.name: getattr(target, f.name) for f in fields(cls)
                      if f.name != "ceiling_target_fingerprint"},
                   ceiling_target_fingerprint=_hash(asdict(target)))


@dataclass(frozen=True, slots=True)
class DeclarationBinding:
    file: str
    owner: str
    name: str
    kind: str
    source_fingerprint: str
    context_fingerprint: str
    declaration_fingerprint: str
    member_span: tuple[int, ...]

    def __post_init__(self):
        for value in (self.file, self.owner, self.name, self.kind, self.source_fingerprint,
                      self.context_fingerprint, self.declaration_fingerprint):
            _text(value)
        _span(self.member_span)


def _span(value):
    if (type(value) is not tuple or len(value) != 2 or any(type(x) is not int for x in value)
            or not 1 <= value[0] <= value[1]):
        _fail("plan_invalid_output", "exact declaration span required")


@dataclass(frozen=True, slots=True)
class PlannedDefinition:
    owner: str
    name: str
    kind: str
    visibility: str
    declared_type: str
    parameters: tuple[tuple[str, str], ...]
    parent: str | None
    roles: tuple[str, ...]
    contract: str
    definition_id: str = ""

    def __post_init__(self):
        _identifier(self.owner)
        _identifier(self.name)
        _text(self.declared_type, empty=True)
        _text(self.contract)
        if not self.definition_id:
            object.__setattr__(self, "definition_id", self.owner + "::" + self.name + "::" + self.kind)
        _text(self.definition_id)
        _tuple(self.parameters, tuple, "parameters")
        _tuple(self.roles, str, "roles")
        if (self.kind not in KINDS or self.visibility not in {"private", "package", "protected", "public"}
                or not self.roles or len(set(self.roles)) != len(self.roles)):
            _fail("plan_invalid_output", "definition shape")
        for parameter in self.parameters:
            if len(parameter) != 2:
                _fail("plan_invalid_output", "parameter shape")
            _text(parameter[0])
            _identifier(parameter[1])
        if self.parent is not None:
            _identifier(self.parent)
        if ((self.kind in {"class", "field"} and self.parameters)
                or (self.kind in {"class", "constructor"} and self.declared_type)
                or (self.kind in {"field", "method"} and not self.declared_type)):
            _fail("plan_invalid_output", "declaration kind/signature mismatch")

    @property
    def identity(self):
        return self.definition_id


@dataclass(frozen=True, slots=True)
class PlannedTarget:
    approved_target: PlanTargetIdentity
    proposed_physical_target: str
    proposed_new_file: bool
    action: str
    definitions: tuple[PlannedDefinition, ...]
    existing_declarations: tuple[DeclarationBinding, ...]
    reason: str
    physical_layout: str = "top_level"
    file_creation_authority: bool = field(default=False, init=False)

    def __post_init__(self):
        if type(self.approved_target) is not PlanTargetIdentity or type(self.proposed_new_file) is not bool:
            _fail("plan_invalid_output", "target mapping shape")
        _tuple(self.definitions, PlannedDefinition, "definitions")
        _tuple(self.existing_declarations, DeclarationBinding, "declarations")
        _text(self.reason)
        _text(self.proposed_physical_target)
        if self.action not in {"create", "add_internal_capability", "modify", "remove"} or not self.definitions:
            _fail("plan_invalid_output", "target action")
        if self.physical_layout not in {"top_level", "nested_in_parent"}:
            _fail("plan_invalid_output", "physical layout")


@dataclass(frozen=True, slots=True)
class CapabilityCoverage:
    code: str
    target: str
    planned_definitions: tuple[str, ...]
    existing_mechanisms: tuple[DeclarationBinding, ...]
    reason: str

    def __post_init__(self):
        _tuple(self.planned_definitions, str, "coverage definitions")
        _tuple(self.existing_mechanisms, DeclarationBinding, "existing mechanisms")
        for value in (self.code, self.target, self.reason):
            _text(value)


@dataclass(frozen=True, slots=True)
class ImplementationDecision:
    area: str
    target: PlanTargetIdentity
    choice: str
    reason: str

    def __post_init__(self):
        if self.area not in AREAS or type(self.target) is not PlanTargetIdentity:
            _fail("plan_invalid_output", "decision vocabulary")
        _text(self.choice)
        _text(self.reason)


@dataclass(frozen=True, slots=True)
class MayTargetSelection:
    target: PlanTargetIdentity
    reason: str


@dataclass(frozen=True, slots=True)
class ValidationEvidenceNeed:
    kind: str
    target: PlanTargetIdentity
    description: str
    proposed_test_file: str | None
    test_write_authority: bool = field(default=False, init=False)

    def __post_init__(self):
        if self.kind not in {"javac", "focused_behavioral_test", "validation_evidence_need"}:
            _fail("plan_invalid_output", "validation needs are not commands")
        if type(self.target) is not PlanTargetIdentity:
            _fail("plan_invalid_output", "validation target")
        _text(self.description)
        if self.proposed_test_file is not None:
            _text(self.proposed_test_file)
            if self.kind != "validation_evidence_need":
                _fail("plan_invalid_output", "unapproved test structure is evidence only")


@dataclass(frozen=True, slots=True)
class PlannerProposal:
    selected_targets: tuple[PlanTargetIdentity, ...]
    logical_creations: tuple[PlannedTarget, ...]
    existing_modifications: tuple[PlannedTarget, ...]
    implementation_decisions: tuple[ImplementationDecision, ...]
    may_targets_selected: tuple[MayTargetSelection, ...]
    ceiling_targets_not_used: tuple[PlanTargetIdentity, ...]
    capability_coverage: tuple[CapabilityCoverage, ...]
    semantic_commitments: tuple[tuple[str, str], ...]
    infrastructure: tuple[str, ...]
    new_semantic_policies: tuple[str, ...]
    savings_credit_guard: str
    inherited_balance_access: str
    base_saving_action: str
    common_savings_contract: bool
    rationale: tuple[str, ...]
    required_validation: tuple[ValidationEvidenceNeed, ...]
    unresolved_plan_issue: str | None
    confidence: float

    def __post_init__(self):
        kinds = {"selected_targets": PlanTargetIdentity, "logical_creations": PlannedTarget,
            "existing_modifications": PlannedTarget, "implementation_decisions": ImplementationDecision,
            "may_targets_selected": MayTargetSelection, "ceiling_targets_not_used": PlanTargetIdentity,
            "capability_coverage": CapabilityCoverage, "semantic_commitments": tuple,
            "infrastructure": str, "new_semantic_policies": str, "rationale": str,
            "required_validation": ValidationEvidenceNeed}
        for name, kind in kinds.items():
            _tuple(getattr(self, name), kind, name)
        for row in self.semantic_commitments:
            if len(row) != 2 or any(type(x) is not str for x in row):
                _fail("plan_invalid_output", "semantic commitment shape")
        if (type(self.confidence) not in {float, int} or not math.isfinite(self.confidence)
                or not 0 <= self.confidence <= 1 or type(self.common_savings_contract) is not bool):
            _fail("plan_invalid_output", "telemetry or contract shape")
        object.__setattr__(self, "confidence", float(self.confidence))
        if self.unresolved_plan_issue is not None:
            _text(self.unresolved_plan_issue)
        for value in (*self.rationale, *self.new_semantic_policies):
            _text(value)

    def as_dict(self):
        return json.loads(_json(asdict(self)))


def _record(cls, raw, nested=None, tuples=()):
    if type(raw) is not dict or set(raw) != {f.name for f in fields(cls)}:
        _fail("plan_invalid_output", "closed " + cls.__name__ + " schema required")
    values = dict(raw)
    for f in fields(cls):
        if not f.init:
            if values.pop(f.name) is not False:
                _fail("plan_invalid_output", "no write authority")
    for key in tuples:
        if type(values[key]) is not list or len(values[key]) > MAX_ITEMS:
            _fail("plan_invalid_output", key)
        values[key] = tuple(tuple(x) if type(x) is list else x for x in values[key])
    for key, convert in (nested or {}).items():
        values[key] = convert(values[key])
    return cls(**values)


def _identity(raw):
    return _record(PlanTargetIdentity, raw, nested={"member_span":
        lambda x: None if x is None else tuple(x)}, tuples=("evidence_refs",))


def _declaration(raw):
    return _record(DeclarationBinding, raw, tuples=("member_span",))


def _list(raw, convert):
    if type(raw) is not list or len(raw) > MAX_ITEMS:
        _fail("plan_invalid_output", "bounded list required")
    return tuple(convert(x) for x in raw)


def normalize_planner_proposal(output):
    """Closed JSON transport, canonical set ordering, parameter order preserved."""
    try:
        raw = output.as_dict() if type(output) is PlannerProposal else output
        encoded = _json(raw)
        if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
            _fail("plan_invalid_output", "output bound exceeded")
        if type(raw) is not dict:
            _fail("plan_output_contains_patch" if type(raw) is str and PATCH_PATTERN.search(raw)
                  else "plan_invalid_output")
        if any(key in raw for key in ("patch", "candidate", "code", "source", "commands")):
            _fail("plan_output_contains_patch")
        # Narrative is explanatory only, but code and material policy are quarantined.
        narrative, strings = [], []
        def collect(value, key=""):
            if type(value) is dict:
                for k, v in value.items():
                    collect(v, k)
            elif type(value) is list:
                for v in value:
                    collect(v, key)
            elif type(value) is str:
                strings.append(value)
                if key in {"reason", "choice", "description", "rationale", "contract"}:
                    narrative.append(value)
        collect(raw)
        if any(PATCH_PATTERN.search(x) for x in strings):
            _fail("plan_output_contains_patch")
        if any(DRIFT_PATTERN.search(x) for x in narrative):
            _fail("plan_semantic_drift", "unbound policy in narrative")
        mapping = lambda x: _record(PlannedTarget, x, nested={
            "approved_target": _identity,
            "definitions": lambda y: _list(y, lambda z: _record(PlannedDefinition, z, tuples=("parameters", "roles"))),
            "existing_declarations": lambda y: _list(y, _declaration)})
        converters = {"selected_targets": lambda x: _list(x, _identity),
            "logical_creations": lambda x: _list(x, mapping), "existing_modifications": lambda x: _list(x, mapping),
            "implementation_decisions": lambda x: _list(x, lambda y: _record(ImplementationDecision, y, nested={"target": _identity})),
            "may_targets_selected": lambda x: _list(x, lambda y: _record(MayTargetSelection, y, nested={"target": _identity})),
            "ceiling_targets_not_used": lambda x: _list(x, _identity),
            "capability_coverage": lambda x: _list(x, lambda y: _record(CapabilityCoverage, y, nested={
                "existing_mechanisms": lambda z: _list(z, _declaration)}, tuples=("planned_definitions",))),
            "required_validation": lambda x: _list(x, lambda y: _record(ValidationEvidenceNeed, y, nested={"target": _identity}))}
        result = _record(PlannerProposal, raw, nested=converters, tuples=("semantic_commitments", "infrastructure",
            "new_semantic_policies", "rationale"))
        normalized = asdict(result)
        # Reconstruct typed records after ordering all set-like lists recursively.
        def order(value, key=""):
            if type(value) is dict:
                return {k: order(v, k) for k, v in value.items()}
            if type(value) in {tuple, list}:
                items = [order(v, "pair" if key in {"parameters", "semantic_commitments"} else "") for v in value]
                return items if key in {"parameters", "member_span", "pair", "evidence_refs"} else sorted(items, key=_json)
            return value
        return _record(PlannerProposal, order(normalized), nested=converters,
            tuples=("semantic_commitments", "infrastructure", "new_semantic_policies", "rationale"))
    except PlanError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError) as exc:
        _fail("plan_invalid_output", type(exc).__name__)


@dataclass(frozen=True, slots=True)
class StructuralImplementationPlan:
    task_fingerprint: str
    effective_design_fingerprint: str
    p1_fingerprint: str
    approval_receipt_fingerprint: str
    approved_ceiling_fingerprint: str
    repository_id: str
    source_bindings: tuple[tuple[str, str, str, str], ...]
    current_scope_fingerprint: str
    current_repair_scope_fingerprint: str
    planner_proposal: PlannerProposal
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    status: str = field(default="validated_read_only_plan", init=False)
    ceiling_targets_not_used_status: str = field(default="ceiling_available_but_unused", init=False)
    authority: str = field(default="read_only_plan", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    file_creation_authority: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)
    repair_scope_delta: int = field(default=0, init=False)
    authoring_scope_delta: int = field(default=0, init=False)
    candidate: None = field(default=None, init=False)
    patch: str = field(default="", init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "plan_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _gate(receipt, stored_human_action, inputs, timings):
    tick = perf_counter()
    try:
        checked = validate_structural_scope_approval_receipt(receipt,
            stored_human_action=stored_human_action, **inputs)
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        reason = str(exc)
        code = ("planning_unavailable" if "not_eligible" in reason or "historical_proposal" in reason
                or "explicit_human" in reason else
                "reacquisition_required" if "reacquisition_required" in reason else "planning_stale")
        _fail(code, reason[:512])
    finally:
        _timed(timings, "approval_validation_seconds", tick)
    if (checked.decision != "approve_exact_scope_ceiling" or checked.eligible_for_admission is not True
            or checked.approval_effect != "eligible_for_admission_only"):
        _fail("planning_unavailable")
    return checked


def _pairs(inputs):
    return ((inputs["current_context"], inputs["current_source"]), *inputs.get("related_contexts", ()))


def declaration_bindings(inputs):
    """Exact declaration inventory from supplied buffers, without acquisition."""
    inventory = []
    for context, raw in _pairs(inputs):
        for kind, members in (("class", (context.class_identity,)), ("field", context.fields),
                ("method", context.methods), ("constructor", context.explicit_constructors)):
            for member in members:
                snippet = raw[member.span.start:member.span.end].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                inventory.append(DeclarationBinding(context.file, context.class_identity.name,
                    member.name, kind, context.source_fingerprint, _hash(context.as_dict()),
                    sha256(snippet.encode()).hexdigest(), (member.span.start_line, member.span.end_line)))
    return tuple(inventory)


def _commitments(inputs):
    design = inputs["scope_transition_effective_design"]
    return tuple(sorted((*( (x.dimension, x.value) for x in design.parent.continuation.typed_answer_commitments),
                         ("existing_savings_transition", design.existing_savings_transition))))


@dataclass(frozen=True, slots=True)
class PlannerContext:
    context_json: str
    authority: str = field(default="read_only_plan", init=False)
    write_authority: bool = field(default=False, init=False)

    @property
    def payload(self):
        return json.loads(self.context_json)


def _context(receipt, inputs, timings):
    tick = perf_counter()
    ceiling = receipt.approved_scope_ceiling
    owners = {t.owner for t in ceiling.existing_targets} | {t.parent for t in ceiling.new_logical_targets if t.parent}
    owners |= {c.target.split("::")[0] for c in ceiling.required_capabilities}
    needed = {(row[0], row[1]) for row in ceiling.source_bindings if row[1] in owners}
    contexts = []
    for context, raw in _pairs(inputs):
        if (context.file, context.class_identity.name) in needed:
            span = context.class_identity.span
            contexts.append({"context": context.as_dict(),
                "exact_class_snippet": raw[span.start:span.end].decode("utf-8")})
    payload = {"boundary": BOUNDARY, "task_fingerprint": receipt.task_contract_fingerprint,
        "repository_id": receipt.repository_id, "source_bindings": receipt.source_bindings,
        "current_scope_fingerprint": receipt.current_scope_fingerprint,
        "effective_design_fingerprint": receipt.effective_design_fingerprint,
        "explicit_semantic_design": inputs["scope_transition_effective_design"].parent.as_dict(),
        "semantic_commitments": _commitments(inputs),
        "resolved_transition": inputs["scope_transition_effective_design"].existing_savings_transition,
        "approved_p1_fingerprint": receipt.proposal_fingerprint,
        "approval_receipt_fingerprint": receipt.fingerprint,
        "approved_ceiling": ceiling.as_dict(), "relevant_class_contexts": contexts,
        "approved_target_identities": [asdict(PlanTargetIdentity.of(x))
            for x in (*ceiling.new_logical_targets, *ceiling.existing_targets)],
        "declarations": [asdict(x) for x in declaration_bindings(inputs) if (x.file, x.owner) in needed],
        "deferred_choices": [asdict(x) for x in ceiling.deferred_decisions],
        "output_schema": {cls.__name__: {f.name: str(f.type) for f in fields(cls)} for cls in
            (PlannerProposal, PlannedTarget, PlannedDefinition, PlanTargetIdentity, DeclarationBinding,
             CapabilityCoverage, ImplementationDecision, MayTargetSelection, ValidationEvidenceNeed)},
        "output_vocabulary": {"decision_areas": sorted(AREAS), "definition_kinds": sorted(KINDS),
            "target_actions": ["create", "add_internal_capability", "modify", "remove"],
            "physical_layouts": ["top_level", "nested_in_parent"],
            "validation_kinds": ["javac", "focused_behavioral_test", "validation_evidence_need"]}}
    encoded = _json(payload)
    if len(encoded.encode("utf-8")) > MAX_CONTEXT_BYTES:
        _fail("planning_context_bounded")
    _timed(timings, "context_projection_seconds", tick)
    return PlannerContext(encoded)


def prepare_structural_implementation_context(*, approval_receipt, stored_human_action, timings=None, **inputs):
    measured = _timings(timings)
    receipt = _gate(approval_receipt, stored_human_action, inputs, measured)
    return _context(receipt, inputs, measured)


def _path(path):
    _text(path)
    if ("\\" in path or ":" in path or "//" in path or PurePosixPath(path).is_absolute()
            or PureWindowsPath(path).is_absolute() or any(p in {"..", ".git", ".agent", ".env"} for p in path.split("/"))
            or str(PurePosixPath(path)) != path or not path.endswith(".java")):
        _fail("plan_outside_approved_ceiling", "unsafe proposed physical target")


def validate_plan_ceiling_containment(proposal, ceiling, *, current_inputs):
    """Exact typed equality, never name prefixes or path-derived authority."""
    approved = {PlanTargetIdentity.of(t) for t in (*ceiling.new_logical_targets, *ceiling.existing_targets)}
    selected = set(proposal.selected_targets)
    unused = set(proposal.ceiling_targets_not_used)
    if (not selected <= approved or not unused <= approved or selected & unused
            or selected | unused != approved or len(selected) != len(proposal.selected_targets)
            or len(unused) != len(proposal.ceiling_targets_not_used)):
        _fail("plan_outside_approved_ceiling")
    mappings = (*proposal.logical_creations, *proposal.existing_modifications)
    if {x.approved_target for x in mappings} != selected or len(mappings) != len(selected):
        _fail("plan_incomplete", "one mapping per selected target required")
    if any(x.target not in approved for x in (*proposal.implementation_decisions, *proposal.required_validation)):
        _fail("plan_outside_approved_ceiling", "decision or validation identity")
    inventory = set(declaration_bindings(current_inputs))
    logical = {PlanTargetIdentity.of(x) for x in ceiling.new_logical_targets}
    for mapping in mappings:
        target = mapping.approved_target
        _path(mapping.proposed_physical_target)
        is_logical = target in logical
        if is_logical != (mapping in proposal.logical_creations):
            _fail("plan_outside_approved_ceiling", "logical/existing category mismatch")
        if is_logical and (mapping.action != "create" or mapping.existing_declarations):
            _fail("plan_outside_approved_ceiling", "logical target cannot modify existing declarations")
        acquired_files = {c.file for c, _ in _pairs(current_inputs)}
        if is_logical and (mapping.proposed_new_file == (mapping.proposed_physical_target in acquired_files)):
            _fail("plan_incomplete", "proposed new file flag contradicts acquired source")
        if not is_logical:
            if mapping.proposed_physical_target != target.file or mapping.proposed_new_file:
                _fail("plan_outside_approved_ceiling", "existing file binding")
            if mapping.action in {"modify", "remove"} and not mapping.existing_declarations:
                _fail("plan_incomplete", "exact modified declarations required")
        for declaration in mapping.existing_declarations:
            if declaration not in inventory:
                _fail("plan_stale", "source/declaration fingerprint mismatch")
            if (declaration.file, declaration.owner) != (target.file, target.owner):
                _fail("plan_outside_approved_ceiling", "declaration owner")
            if target.declaration_fingerprint and (declaration.declaration_fingerprint != target.declaration_fingerprint
                    or declaration.member_span != target.member_span or declaration.name != target.name):
                _fail("plan_outside_approved_ceiling", "exact existing declaration identity")
            if mapping.action not in {"modify", "remove"} or not any(
                    d.name == declaration.name and d.kind == declaration.kind for d in mapping.definitions):
                _fail("plan_incomplete", "modified declaration has no concrete definition mapping")
        allowed_types = {"void", "boolean", "byte", "short", "int", "long", "float", "double", "char",
            "String", "Boolean", "Byte", "Short", "Integer", "Long", "Float", "Double", "Character"}
        allowed_types.update(x.owner for x in approved)
        def allowed_type(value):
            return value.removesuffix("[]").removeprefix("java.lang.") in allowed_types
        for definition in mapping.definitions:
            if definition.owner != target.owner:
                _fail("plan_outside_approved_ceiling", "unapproved third class")
            if ((definition.declared_type and not allowed_type(definition.declared_type))
                    or any(not allowed_type(t) for t, _ in definition.parameters)):
                _fail("plan_outside_approved_ceiling", "unapproved type or infrastructure dependency")
            if target.kind == "new_class":
                if definition.kind not in {"class", "constructor"} or definition.name != target.name or (
                        definition.kind == "class" and definition.parent != target.parent):
                    _fail("plan_outside_approved_ceiling", "logical class/parent mapping")
                if (definition.kind == "class" and definition.visibility == "public" and mapping.physical_layout == "top_level"
                        and PurePosixPath(mapping.proposed_physical_target).name != definition.name + ".java"):
                    _fail("plan_incomplete", "public top-level Java declaration requires a matching proposed filename")
                if definition.kind == "class" and mapping.physical_layout == "top_level" and definition.visibility not in {"public", "package"}:
                    _fail("plan_incomplete", "top-level Java visibility is not source compatible")
            if target.kind == "new_field_required" and (definition.kind != "field" or definition.name != target.name):
                _fail("plan_outside_approved_ceiling", "required logical field identity")
            if target.kind == "existing_method" and (definition.kind != "method" or definition.name != target.name):
                _fail("plan_outside_approved_ceiling", "existing method identity")
    # All logical pieces of one class share one proposed location and new-file intent.
    for owner in {x.approved_target.owner for x in proposal.logical_creations}:
        locations = {(x.proposed_physical_target, x.proposed_new_file, x.physical_layout) for x in proposal.logical_creations
                     if x.approved_target.owner == owner}
        if len(locations) != 1:
            _fail("plan_incomplete", "inconsistent logical-to-physical mapping")
    for need in proposal.required_validation:
        if need.proposed_test_file is not None:
            _path(need.proposed_test_file)
    required_logical = {PlanTargetIdentity.of(x) for x in ceiling.new_logical_targets if x.category == "MUST_CREATE_LOGICAL"}
    required_existing = {PlanTargetIdentity.of(x) for x in ceiling.existing_targets if x.category == "MUST_EDIT_EXISTING"}
    if not (required_logical | required_existing) <= selected:
        _fail("plan_incomplete", "required structural mapping missing")
    may = {x for x in approved if x.category == "MAY_REQUIRE_EXISTING_API_CHANGE"}
    if {x.target for x in proposal.may_targets_selected} != selected & may or len(proposal.may_targets_selected) != len(selected & may):
        _fail("plan_incomplete", "MAY selection accounting")
    for choice in proposal.may_targets_selected:
        _text(choice.reason)
    return True


def _sufficient_debit(binding, inputs):
    for context, raw in _pairs(inputs):
        if (context.file, context.class_identity.name) == (binding.file, binding.owner):
            balances = [x for x in context.fields if x.name == "balance"]
            for method in context.methods:
                if method.name == binding.name and (method.span.start_line, method.span.end_line) == binding.member_span and len(balances) == 1:
                    return _debit_suitability(context, raw, method, balances[0])[0] == "sufficient"
    return False


def _semantics(proposal, ceiling, inputs):
    if proposal.new_semantic_policies or proposal.infrastructure != ("in_memory",):
        _fail("plan_semantic_drift", "new policy or forbidden infrastructure")
    if tuple(sorted(proposal.semantic_commitments)) != _commitments(inputs):
        _fail("plan_semantic_drift", "effective semantic commitments changed")
    if proposal.unresolved_plan_issue:
        _fail("semantic_clarification_required", proposal.unresolved_plan_issue)
    if proposal.savings_credit_guard != "successful_inherited_debit" or proposal.inherited_balance_access != "encapsulated":
        _fail("plan_semantic_drift", "funding or encapsulation changed")
    transition = inputs["scope_transition_effective_design"].existing_savings_transition
    if ((transition == "savings_only_on_subclass" and proposal.base_saving_action not in {"remove", "retire_from_intended_api"})
            or (transition == "preserve_base_compatibility" and proposal.base_saving_action != "preserve")
            or (transition == "subclass_specialization" and (proposal.base_saving_action != "preserve_and_specialize"
                                                          or proposal.common_savings_contract is not True))):
        _fail("plan_semantic_drift", "chosen savings transition changed")
    mappings = (*proposal.logical_creations, *proposal.existing_modifications)
    definitions = {d.identity: d for x in mappings for d in x.definitions}
    if len(definitions) != sum(len(x.definitions) for x in mappings):
        _fail("plan_scope_nonminimal", "duplicate definitions")
    must = {(x.code, x.target): x for x in ceiling.required_capabilities if x.certainty == "MUST_SUPPORT"}
    if any(not set(d.roles) <= {code for code, _ in must} for d in definitions.values()):
        _fail("plan_semantic_drift", "definition introduces an unbound semantic role")
    coverage = {(x.code, x.target): x for x in proposal.capability_coverage}
    if set(coverage) != set(must) or len(coverage) != len(proposal.capability_coverage):
        _fail("plan_incomplete", "all MUST capabilities require coverage")
    inventory = set(declaration_bindings(inputs))
    shape = {"new_subtype_definition": {"class"}, "subclass_initialization": {"constructor"},
        "subclass_owned_state": {"field"}, "credential_state": {"field", "method"},
        "authentication_gated_savings_operation": {"method"}, "savings_funding_transition": {"method"},
        "base_balance_debit": {"method"}, "savings_interest_behavior": {"method"},
        "existing_savings_transition": {"method"}}
    for key, entry in coverage.items():
        code, target = key
        if not entry.planned_definitions and not entry.existing_mechanisms:
            _fail("plan_incomplete", "empty capability coverage")
        if len(set(entry.planned_definitions)) != len(entry.planned_definitions):
            _fail("plan_scope_nonminimal", "duplicate capability mapping")
        for ref in entry.planned_definitions:
            d = definitions.get(ref)
            if d is None or code not in d.roles or d.kind not in shape.get(code, KINDS):
                _fail("plan_incomplete", "capability/definition mapping")
            expected_owner = target.split("::")[0]
            initialization_parents = {r.parent for r in inputs["scope_transition_effective_design"].relationships
                                      if r.child == expected_owner}
            if (code != "existing_savings_transition" and d.owner != expected_owner
                    and not (code == "subclass_initialization" and d.owner in initialization_parents)):
                _fail("plan_semantic_drift", "capability owner mismatch")
            if code == "base_balance_debit" and d.contract != "observable_atomic_successful_debit":
                _fail("plan_incomplete", "successful debit contract missing")
            if code == "subclass_owned_state" and d.name != target.split("::")[-1]:
                _fail("plan_semantic_drift", "required state identity changed")
            if code == "subclass_initialization" and d.contract != "compatible_base_constructor_initialization":
                _fail("plan_incomplete", "compatible base initialization missing")
            if code == "credential_state" and d.contract != "simple_in_memory_password":
                _fail("plan_semantic_drift", "credential representation changed")
            if code == "authentication_gated_savings_operation" and d.contract != "operation_gated_password_verification":
                _fail("plan_incomplete", "authentication gate missing")
            if code == "savings_funding_transition" and d.contract != "credit_only_after_successful_inherited_debit":
                _fail("plan_incomplete", "credit/debit ordering missing")
            if code == "savings_interest_behavior" and d.contract != "interest_on_saving_balance_only":
                _fail("plan_semantic_drift", "interest semantics changed")
        for binding in entry.existing_mechanisms:
            if binding not in inventory:
                _fail("plan_stale", "existing mechanism declaration changed")
            if binding.owner != target.split("::")[0]:
                _fail("plan_outside_approved_ceiling", "existing mechanism owner")
            if code == "base_balance_debit":
                if not _sufficient_debit(binding, inputs):
                    _fail("plan_incomplete", "current void withdrawal does not prove successful debit")
            elif code == "existing_savings_transition":
                if binding.name != target.split("::")[-1] or transition == "savings_only_on_subclass":
                    _fail("plan_semantic_drift", "base savings cannot remain intended subclass-only behavior")
            elif code == "subclass_initialization":
                if binding.kind != "constructor":
                    _fail("plan_incomplete", "initialization mechanism")
            else:
                _fail("plan_incomplete", "existing mechanism has no deterministic semantic proof")
    base_edits = [x for x in proposal.existing_modifications if x.approved_target.name == "saving"]
    if transition != "savings_only_on_subclass" and any(x.action == "remove" for x in base_edits):
        _fail("plan_semantic_drift", "required base saving removed")
    if transition == "savings_only_on_subclass" and not base_edits:
        _fail("plan_incomplete", "base savings transition not mapped")
    if transition == "savings_only_on_subclass" and proposal.base_saving_action == "remove" and any(
            x.action != "remove" for x in base_edits):
        _fail("plan_semantic_drift", "retirement proposal contradicts its edit mapping")
    if transition == "subclass_specialization":
        base_methods = [m for context, _ in _pairs(inputs) for m in context.methods
                        if context.class_identity.name == "BankAccount" and m.name == "saving"]
        specialized = [d for d in definitions.values() if "savings_interest_behavior" in d.roles]
        if not any(d.name == m.name and d.declared_type == m.return_type and
                   tuple(t for t, _ in d.parameters) == tuple(p.declared_type for p in m.parameters)
                   for d in specialized for m in base_methods):
            _fail("plan_incomplete", "common savings contract lacks compatible specialization")
        if any(m.is_final or m.visibility == "private" for m in base_methods) and not any(
                x.approved_target.name == "savings_specialization_capability" for x in proposal.existing_modifications):
            _fail("plan_incomplete", "current base declaration blocks specialization")
    class_mappings = [x for x in proposal.logical_creations if x.approved_target.kind == "new_class"]
    for mapping in class_mappings:
        parent = mapping.approved_target.parent
        contexts = [c for c, _ in _pairs(inputs) if c.class_identity.name == parent]
        nested = mapping.physical_layout == "nested_in_parent"
        if nested and (not contexts or mapping.proposed_new_file or mapping.proposed_physical_target != contexts[0].file):
            _fail("plan_outside_approved_ceiling", "nested definition requires exact parent source")
        if contexts and contexts[0].explicit_constructors and all(
                c.visibility == "private" for c in contexts[0].explicit_constructors) and not nested:
            if not any(x.approved_target.name == "subclass_initialization_capability" for x in proposal.existing_modifications):
                _fail("plan_incomplete", "private base construction path unresolved")
    needed_areas = {"source_layout", "constructor", "state", "credential", "savings_funding",
                    "savings_interest", "existing_saving_transition", "debit"}
    if not needed_areas <= {x.area for x in proposal.implementation_decisions} or not proposal.required_validation:
        _fail("plan_incomplete", "deferred implementation decisions or validation strategy missing")
    return definitions, coverage


def _minimality(proposal, definitions, coverage, inputs):
    # Bounded structural deletion check, independent of textual PATCH.MINIMAL.
    # Coverage may be a conjunction of several definitions, not just one witness.
    used = {ref for c in coverage.values() for ref in c.planned_definitions}
    if set(definitions) != used:
        _fail("plan_scope_nonminimal", "unneeded planned definition")
    for mapping in (*proposal.logical_creations, *proposal.existing_modifications):
        if not any(d.identity in used for d in mapping.definitions):
            _fail("plan_scope_nonminimal", "selected target has no required capability witness")
        if mapping.approved_target.name == "successful_balance_debit_capability":
            if any(d.visibility == "public" for d in mapping.definitions):
                _fail("plan_scope_nonminimal", "narrower internal debit mechanism suffices")
            if any(_sufficient_debit(b, inputs) for b in declaration_bindings(inputs)
                   if b.kind == "method" and b.owner == mapping.approved_target.owner):
                _fail("plan_scope_nonminimal", "existing successful debit already sufficient")
        if mapping.approved_target.name == "saving" and inputs["scope_transition_effective_design"].existing_savings_transition != "savings_only_on_subclass":
            _fail("plan_scope_nonminimal", "preserved base savings already satisfies its contract")
        if mapping.approved_target.name == "subclass_initialization_capability":
            if any(x.physical_layout == "nested_in_parent" and x.approved_target.parent == mapping.approved_target.owner
                   for x in proposal.logical_creations if x.approved_target.kind == "new_class"):
                _fail("plan_scope_nonminimal", "nested layout already permits private base construction")
            if any(d.visibility == "public" for d in mapping.definitions):
                _fail("plan_scope_nonminimal", "narrower constructor access suffices")


def _build(receipt, output, inputs, timings):
    tick = perf_counter()
    proposal = normalize_planner_proposal(output)
    _timed(timings, "plan_normalization_seconds", tick)
    if proposal.unresolved_plan_issue:
        _fail("semantic_clarification_required", proposal.unresolved_plan_issue)
    tick = perf_counter()
    validate_plan_ceiling_containment(proposal, receipt.approved_scope_ceiling, current_inputs=inputs)
    _timed(timings, "ceiling_containment_seconds", tick)
    tick = perf_counter()
    definitions, coverage = _semantics(proposal, receipt.approved_scope_ceiling, inputs)
    _timed(timings, "semantic_validation_seconds", tick)
    tick = perf_counter()
    _minimality(proposal, definitions, coverage, inputs)
    _timed(timings, "plan_minimality_seconds", tick)
    return StructuralImplementationPlan(receipt.task_contract_fingerprint, receipt.effective_design_fingerprint,
        receipt.proposal_fingerprint, receipt.fingerprint, receipt.approved_scope_ceiling_fingerprint,
        receipt.repository_id, receipt.source_bindings, receipt.current_scope_fingerprint,
        receipt.current_repair_scope_fingerprint, proposal)


def build_structural_implementation_plan(*, approval_receipt, stored_human_action, planner_output, timings=None, **inputs):
    """Synthetic/pure path: zero model calls, fresh approval checked first."""
    measured = _timings(timings)
    started = perf_counter()
    try:
        receipt = _gate(approval_receipt, stored_human_action, inputs, measured)
        _context(receipt, inputs, measured)
        return _build(receipt, planner_output, inputs, measured)
    finally:
        measured["total_deterministic_seconds"] = perf_counter() - started


def validate_structural_implementation_plan(plan, *, approval_receipt, stored_human_action, **inputs):
    """Pure later-ADMIT seam: reconstruct everything, including canonical hash."""
    payload = plan.as_dict() if type(plan) is StructuralImplementationPlan else plan
    if type(payload) is not dict or "planner_proposal" not in payload:
        _fail("plan_invalid_output", "typed plan required")
    if payload.get("candidate") is not None or payload.get("patch") != "":
        _fail("plan_output_contains_patch")
    expected = build_structural_implementation_plan(approval_receipt=approval_receipt,
        stored_human_action=stored_human_action, planner_output=payload["planner_proposal"], **inputs)
    if _json(payload) != _json(expected.as_dict()):
        _fail("plan_stale", "plan fingerprint, freshness or authority mismatch")
    return expected


class ReadOnlyImplementationPlanner(Protocol):
    def plan(self, context: PlannerContext) -> PlannerProposal | dict: ...


@dataclass(frozen=True, slots=True)
class ImplementationPlanningResult:
    status: str
    plan: StructuralImplementationPlan | None
    reason: str
    model_calls: int
    authority: str = field(default="read_only_plan", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    repair_scope_delta: int = field(default=0, init=False)
    authoring_scope_delta: int = field(default=0, init=False)
    candidate: None = field(default=None, init=False)
    patch: str = field(default="", init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)


def plan_structural_implementation(*, approval_receipt, stored_human_action,
        planner: ReadOnlyImplementationPlanner, planning_call_authorized=False, timings=None, **inputs):
    """An eligible operation gets at most one already authorized planner call.

    Provider transport is injected by the caller; this seam never selects an
    author, retries, resamples, or falls back to deterministic API design.
    """
    measured = _timings(timings)
    started = perf_counter()
    calls = 0
    try:
        receipt = _gate(approval_receipt, stored_human_action, inputs, measured)
        context = _context(receipt, inputs, measured)
        if planning_call_authorized is not True:
            _fail("planning_call_not_authorized")
        if planner is None or not callable(getattr(planner, "plan", None)):
            _fail("planning_provider_unavailable")
        tick = perf_counter()
        calls = 1
        try:
            output = planner.plan(context)
        except Exception:
            # Do not retain exception text or provider output as authority/evidence.
            _fail("planning_provider_failure")
        finally:
            _timed(measured, "planner_call_seconds", tick)
        plan = _build(receipt, output, inputs, measured)
        return ImplementationPlanningResult(plan.status, plan, "validated", calls)
    except PlanError as exc:
        return ImplementationPlanningResult(exc.code, None, exc.reason, calls)
    finally:
        measured["total_deterministic_seconds"] = max(0.0,
            perf_counter() - started - measured["planner_call_seconds"])
