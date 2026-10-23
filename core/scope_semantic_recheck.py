"""PATCH.SCOPE.RECHECK.1: scope-discovered meaning, never scope admission.

The old proposal is reconstructed before any question is authorized. A human
answer appends a semantic revision to CONTINUE.1; it cannot change its parent,
create a source target, or turn a proposal into an authoring scope. All source
buffers and intent evidence are supplied by the caller. No intake or I/O.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re
from time import perf_counter

from core.clarification_answer_evidence import AnswerConflict, extract_clarification_answer
from core.design_intent_continuation import EffectiveProposedDesignIntent
from core.explicit_design_evidence import EvidenceSpan
from core.oop_intent_detector import detect_missing_future_design_contract
from core.oop_intent_session import bind_human_answer
from core.oop_semantic_review import OOPIntentAlternative, OOPIntentGap
from core.structural_scope_expansion import (
    StructuralScopeExpansionProposal, detection_fingerprint,
    propose_structural_scope_expansion,
)

PHASE_ID = "PATCH.SCOPE.RECHECK.1"
SCHEMA_VERSION = "patch_scope_recheck_1_v1"
DIMENSION = "existing_savings_transition"
TRANSITION_VALUES = frozenset({"savings_only_on_subclass", "preserve_base_compatibility",
                               "subclass_specialization"})
TIMING_FIELDS = ("proposal_validation_seconds", "transition_classification_seconds",
                "gap_construction_seconds", "answer_projection_seconds",
                "semantic_recheck_seconds", "total_seconds")


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True, slots=True)
class TransitionAssessment:
    target: str
    decision: str
    disposition: str
    reason: str

    def __post_init__(self):
        if self.disposition not in {"implementation_only", "human_owned_material_semantics", "resolved"}:
            raise ValueError("invalid_transition_disposition")


@dataclass(frozen=True, slots=True)
class ScopeSemanticRecheck:
    status: str
    proposal_fingerprint: str = ""
    effective_design_fingerprint: str = ""
    task_contract_fingerprint: str = ""
    repository_id: str = ""
    source_fingerprint: str = ""
    source_path: str = ""
    class_identity: str = ""
    declaration_fingerprints: tuple[str, ...] = ()
    assessments: tuple[TransitionAssessment, ...] = ()
    possible_intent_gaps: tuple[OOPIntentGap, ...] = ()
    reasons: tuple[str, ...] = ()
    scope_refresh_required: bool = False
    transition_continuation_fingerprint: str = ""
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    authority: str = field(default="read_only", init=False)
    scope_authority: str = field(default="proposal_only", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)
    author_calls: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    authoring_scope_delta: int = field(default=0, init=False)
    candidate: None = field(default=None, init=False)
    patch: str = field(default="", init=False)

    def __post_init__(self):
        if self.status not in {"clarification_required", "no_gap", "semantic_recheck_not_required",
                               "invalid_proposal", "reacquisition_required", "bounded",
                               "continuation_conflict", "answer_projection_bounded"}:
            raise ValueError("invalid_recheck_status")
        if (not isinstance(self.possible_intent_gaps, tuple) or len(self.possible_intent_gaps) > 1
                or any(not isinstance(g, OOPIntentGap) for g in self.possible_intent_gaps)
                or (self.status == "clarification_required") != bool(self.possible_intent_gaps)):
            raise ValueError("invalid_recheck_gap_partition")
        if (not isinstance(self.declaration_fingerprints, tuple) or len(self.declaration_fingerprints) > 32
                or any(not _sha(x) for x in self.declaration_fingerprints)
                or not isinstance(self.assessments, tuple) or len(self.assessments) > 80
                or any(not isinstance(x, TransitionAssessment) for x in self.assessments)):
            raise ValueError("invalid_recheck_bounds")

    @property
    def gap(self):
        return self.possible_intent_gaps[0] if self.possible_intent_gaps else None

    @property
    def first_remaining_blocker(self):
        if self.gap:
            return "human_clarification_required"
        return "SCOPE_REFRESH_REQUIRED" if self.scope_refresh_required else self.status.upper()

    def as_dict(self):
        return json.loads(_json({**asdict(self), "phase_id": PHASE_ID,
                               "first_remaining_blocker": self.first_remaining_blocker}))

    @property
    def fingerprint(self):
        return _hash(self.as_dict())


@dataclass(frozen=True, slots=True)
class ScopeTransitionCommitment:
    value: str
    evidence: EvidenceSpan
    answer_fingerprint: str
    dimension: str = field(default=DIMENSION, init=False)
    provenance: str = field(default="explicit_human", init=False)

    def __post_init__(self):
        if (self.value not in TRANSITION_VALUES or not isinstance(self.evidence, EvidenceSpan)
                or self.evidence.provenance != "explicit_human" or not _sha(self.answer_fingerprint)):
            raise ValueError("invalid_scope_transition_commitment")

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScopeTransitionContinuation:
    status: str
    parent_design_fingerprint: str
    parent_continuation_fingerprint: str
    parent_gap_id: str
    proposal_fingerprint: str
    task_contract_fingerprint: str
    answer_fingerprint: str
    answer_record_fingerprint: str
    repository_id: str
    source_path: str
    source_fingerprint: str
    class_identity: str
    declaration_fingerprints: tuple[str, ...]
    typed_answer_commitments: tuple[ScopeTransitionCommitment, ...]
    resolved_dimensions: tuple[str, ...]
    remaining_dimensions: tuple[str, ...]
    conflicts: tuple[AnswerConflict, ...] = ()
    not_resolved_by_continuation: tuple[EvidenceSpan, ...] = ()
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    provenance: str = field(default="explicit_human", init=False)
    authority: str = field(default="read_only", init=False)
    scope_authority: str = field(default="proposal_only", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)

    def __post_init__(self):
        if self.status not in {"clarification_projected", "answer_projection_bounded", "continuation_conflict"}:
            raise ValueError("invalid_transition_continuation_status")
        for key in ("parent_design_fingerprint", "parent_continuation_fingerprint", "parent_gap_id", "proposal_fingerprint",
                    "task_contract_fingerprint", "answer_fingerprint", "answer_record_fingerprint",
                    "source_fingerprint"):
            if not _sha(getattr(self, key)):
                raise ValueError("invalid_transition_continuation_binding")
        for key, kind, limit in (("typed_answer_commitments", ScopeTransitionCommitment, 1),
                ("resolved_dimensions", str, 1), ("remaining_dimensions", str, 1),
                ("declaration_fingerprints", str, 32), ("conflicts", AnswerConflict, 64),
                ("not_resolved_by_continuation", EvidenceSpan, 48)):
            rows = getattr(self, key)
            if not isinstance(rows, tuple) or len(rows) > limit or any(not isinstance(x, kind) for x in rows):
                raise ValueError("invalid_transition_continuation_bounds")
        projected = self.status == "clarification_projected"
        if (self.resolved_dimensions != ((DIMENSION,) if projected else ())
                or self.remaining_dimensions != (() if projected else (DIMENSION,))
                or projected != bool(self.typed_answer_commitments)
                or (self.status == "continuation_conflict") != bool(self.conflicts)
                or any(not _sha(x) for x in self.declaration_fingerprints)):
            raise ValueError("invalid_transition_continuation_partition")

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    @property
    def continuation_fingerprint(self):
        return self.fingerprint

    def as_dict(self):
        return json.loads(_json({**asdict(self), "continuation_fingerprint": self.fingerprint}))


@dataclass(frozen=True, slots=True)
class ScopeTransitionEffectiveDesign:
    """Append one semantic revision, keeping DESIGN.1 and CONTINUE.1 intact.

    This facade is deliberately not a frozen EXPAND.1 accepted input type.
    A future planner must explicitly handle the new meaning and re-propose.
    """
    parent: EffectiveProposedDesignIntent
    transition: ScopeTransitionContinuation
    authority: str = field(default="read_only", init=False)
    scope_authority: str = field(default="proposal_only", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)

    def __post_init__(self):
        if (not isinstance(self.parent, EffectiveProposedDesignIntent)
                or not isinstance(self.transition, ScopeTransitionContinuation)
                or self.parent.fingerprint != self.transition.parent_design_fingerprint
                or self.parent.continuation.fingerprint != self.transition.parent_continuation_fingerprint):
            raise ValueError("transition_parent_design_mismatch")

    @property
    def existing_savings_transition(self):
        if self.transition.status != "clarification_projected":
            return None
        return self.transition.typed_answer_commitments[0].value

    @property
    def status(self):
        return {"clarification_projected": self.parent.status,
                "continuation_conflict": "conflict", "answer_projection_bounded": "bounded"}[self.transition.status]

    def __getattr__(self, name):
        if name in {"relationships", "state_commitments", "behavior_gates", "explicit_absences",
                    "task_contract_fingerprint", "unresolved_dimensions", "authority",
                    "write_authority", "execution_authorized", "auto_apply", "repair_scope_authority"}:
            return getattr(self.parent, name)
        raise AttributeError(name)

    def as_dict(self):
        return {"schema_version": SCHEMA_VERSION, "parent": self.parent.as_dict(),
                "transition": self.transition.as_dict(), "status": self.status,
                "existing_savings_transition": self.existing_savings_transition,
                "scope_refresh_required": self.existing_savings_transition is not None,
                "scope_authority": "proposal_only", "write_authority": False,
                "execution_authorized": False, "auto_apply": False, "repair_scope_authority": False}

    @property
    def fingerprint(self):
        return _hash(self.as_dict())


def compose_scope_transition_design(design_intent, continuation):
    return ScopeTransitionEffectiveDesign(design_intent, continuation)


def recheck_scope_semantics(*, proposal, task_contract, design_intent, semantic_detection,
        current_context, current_source, repository_id, repo_path=None, stored_gap=None,
        stored_answer=None, current_scope=None, expected_scope_fingerprint=None,
        related_contexts=(), transition_continuation=None, stored_transition_gap=None,
        stored_transition_answer=None, timings=None):
    """Inspect only explicit transition candidates in a reconstructed proposal.

    After an answer the old proposal is validated as historical evidence only.
    It is never represented as current scope authority for the revised design.
    """
    started = perf_counter()
    elapsed = {key: 0.0 for key in TIMING_FIELDS}
    bindings = {}

    def finish(status, **fields):
        elapsed["total_seconds"] = perf_counter() - started
        if timings is not None:
            timings.update(elapsed)
        return ScopeSemanticRecheck(status, **{**bindings, **fields})

    tick = perf_counter()
    try:
        if not isinstance(proposal, StructuralScopeExpansionProposal):
            raise ValueError("typed_proposal_required")
        if not isinstance(design_intent, EffectiveProposedDesignIntent):
            raise ValueError("typed_effective_design_required")
        # Reject stale questions before reconstructing either receipt.
        contexts = ((current_context, current_source), *related_contexts)
        if any(not isinstance(raw, bytes) or sha256(raw).hexdigest() != c.source_fingerprint
               for c, raw in contexts):
            return finish("reacquisition_required", reasons=("current_source_changed",))
        if any((c.file, c.class_identity.qualified_name, c.source_fingerprint)
               not in {row[:3] for row in proposal.source_bindings} for c, _ in contexts):
            return finish("reacquisition_required", reasons=("proposal_source_changed",))
        if semantic_detection.status != "no_gap":
            raise ValueError("validated_no_gap_receipt_required")
        # The original receipt is reconstructed from frozen typed intent and
        # its original answer evidence, never independent raw task intake.
        receipt = detect_missing_future_design_contract(task_contract=task_contract,
            design_intent=design_intent, current_context=current_context,
            current_source=current_source, repository_id=repository_id,
            repo_path=repo_path, stored_gap=stored_gap, stored_answer=stored_answer)
        if receipt.status != "no_gap" or detection_fingerprint(receipt) != detection_fingerprint(semantic_detection):
            raise ValueError("no_gap_receipt_reconstruction_mismatch")
        inputs = dict(task_contract=task_contract, design_intent=design_intent,
            semantic_detection=semantic_detection, current_context=current_context,
            current_source=current_source, repository_id=repository_id,
            current_scope=current_scope, expected_scope_fingerprint=expected_scope_fingerprint,
            related_contexts=related_contexts)
        reconstructed = propose_structural_scope_expansion(**inputs)
        if reconstructed.status == "reacquisition_required":
            return finish("reacquisition_required", reasons=reconstructed.reasons)
        if reconstructed.proposal is None or reconstructed.proposal.to_json() != proposal.to_json():
            raise ValueError("stale_or_forged_scope_proposal")
        bindings = dict(proposal_fingerprint=proposal.fingerprint,
            effective_design_fingerprint=design_intent.fingerprint,
            task_contract_fingerprint=proposal.task_contract_fingerprint,
            repository_id=repository_id, source_fingerprint=current_context.source_fingerprint,
            source_path=current_context.file, class_identity=current_context.class_identity.qualified_name)
        elapsed["proposal_validation_seconds"] = perf_counter() - tick

        tick = perf_counter()
        marked = {x.target for x in proposal.required_capabilities if x.certainty == "NEEDS_TRANSITION_DECISION"}
        candidates = tuple(x for x in proposal.deferred_decisions
                           if x.semantic_recheck_if_behavior_changes or x.target in marked)
        # A capability may mark a candidate even without a deferred row.
        assessments = []
        material_targets = set(marked)
        material_targets.update(x.target for x in candidates if x.decision == DIMENSION)
        for item in candidates:
            is_transition = item.target in marked and item.decision == DIMENSION
            assessments.append(TransitionAssessment(item.target, item.decision,
                "human_owned_material_semantics" if is_transition else "implementation_only",
                "different_future_API_ownership_and_compatibility_commitments" if is_transition
                else "code_shape_does_not_change_requested_domain_behavior"))
        material = [c for c in proposal.required_capabilities
                    if c.target in material_targets and c.code == DIMENSION
                    and c.certainty == "NEEDS_TRANSITION_DECISION"]
        if not candidates and not marked:
            elapsed["transition_classification_seconds"] = perf_counter() - tick
            return finish("semantic_recheck_not_required", reasons=("no_marked_transition_item",))
        if not material:
            elapsed["transition_classification_seconds"] = perf_counter() - tick
            return finish("no_gap", assessments=tuple(assessments), reasons=("implementation_only",))
        # Materiality uses exact typed ownership and source write relations.
        states = [s for s in design_intent.state_commitments if s.state_role == "savings_state"
                  and s.base_exclusion and s.owner != s.base_exclusion]
        values = {x.dimension: x.value for x in design_intent.continuation.typed_answer_commitments}
        selected = [s for s in states if any(c.target == s.base_exclusion + "::saving" for c in material)]
        if (len(selected) != 1 or values.get("savings_interest_semantics") != "interest_applies_to_saving_balance"
                or selected[0].base_exclusion != current_context.class_identity.name):
            raise ValueError("unsupported_material_transition_evidence")
        state = selected[0]
        methods = [m for m in current_context.methods if m.name == "saving" and any(
            r.method_span == m.span and r.field_name == "balance" and r.access in {"write", "read_write"}
            for r in current_context.relations)]
        declarations = tuple(sorted({sha256(current_source[m.span.start:m.span.end].decode("utf-8")
            .replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest() for m in methods}))
        targets = [t for t in proposal.existing_targets if t.target == state.base_exclusion + "::saving"]
        if not declarations or {t.declaration_fingerprint for t in targets} != set(declarations):
            raise ValueError("exact_saving_declaration_binding_required")
        bindings["declaration_fingerprints"] = declarations
        if not assessments:
            assessments.append(TransitionAssessment(material[0].target, DIMENSION,
                "human_owned_material_semantics", "different_future_API_ownership_and_compatibility_commitments"))
        elapsed["transition_classification_seconds"] = perf_counter() - tick

        tick = perf_counter()
        refs = ("scope_proposal:" + proposal.fingerprint, "effective_design:" + design_intent.fingerprint,
                "saving_declarations:" + _hash(declarations), "current_source:" + current_context.source_fingerprint,
                "task_contract:" + proposal.task_contract_fingerprint, "repository:" + _hash(repository_id))
        gap = OOPIntentGap(dimension=DIMENSION,
            question=(f"{state.base_exclusion} currently has saving(...) that modifies its ordinary balance. "
                      f"Your future design puts savings state and interest behavior on {state.owner}. "
                      f"What should the existing {state.base_exclusion}.saving behavior mean in the future?"),
            alternatives=(
                OOPIntentAlternative("savings_only_on_subclass",
                    "Savings functionality should exist only on SavingAccount; base savings behavior should no longer be part of the intended API."),
                OOPIntentAlternative("preserve_base_compatibility",
                    "Keep the existing BankAccount saving behavior for compatibility, while SavingAccount has its own savings-state behavior."),
                OOPIntentAlternative("subclass_specialization",
                    "Keep a base savings contract but let SavingAccount specialize its behavior to use savingBalance."),
                OOPIntentAlternative("another_compatibility_rule", "Another intended compatibility rule; describe its meaning.")),
            evidence_refs=refs, source_fingerprint=current_context.source_fingerprint,
            task_fingerprint=sha256(task_contract.raw_request.text.encode("utf-8")).hexdigest())
        elapsed["gap_construction_seconds"] = perf_counter() - tick
        if transition_continuation is None:
            return finish("clarification_required", assessments=tuple(assessments), possible_intent_gaps=(gap,))

        # Reconstruct the entire new answer revision against the OLD inputs.
        # This is historical validation, not reuse of old proposed scope.
        tick = perf_counter()
        answer_timings = {}
        expected = continue_scope_transition(proposal=proposal, **inputs_without_proposal(inputs),
            repo_path=repo_path, stored_gap=stored_gap, stored_answer=stored_answer,
            stored_transition_gap=stored_transition_gap, stored_transition_answer=stored_transition_answer,
            timings=answer_timings)
        if not isinstance(transition_continuation, ScopeTransitionContinuation) or expected.as_dict() != transition_continuation.as_dict():
            raise ValueError("forged_transition_continuation")
        elapsed["answer_projection_seconds"] = answer_timings["answer_projection_seconds"]
        if expected.status != "clarification_projected":
            return finish(expected.status, assessments=tuple(assessments), reasons=("transition_meaning_unresolved",))
        effective = compose_scope_transition_design(design_intent, expected)
        resolved = tuple(TransitionAssessment(a.target, a.decision,
            "resolved" if a.disposition == "human_owned_material_semantics" else a.disposition,
            "provenance_bound_human_transition_meaning" if a.disposition == "human_owned_material_semantics" else a.reason)
            for a in assessments)
        elapsed["semantic_recheck_seconds"] = perf_counter() - tick
        return finish("no_gap", effective_design_fingerprint=effective.fingerprint, assessments=resolved,
            scope_refresh_required=True, transition_continuation_fingerprint=expected.fingerprint,
            reasons=("scope_transition_resolved", "old_proposal_is_historical_only", "scope_reproposal_required"))
    except (ValueError, TypeError, AttributeError, KeyError, UnicodeError) as exc:
        elapsed["proposal_validation_seconds"] = elapsed["proposal_validation_seconds"] or perf_counter() - tick
        return finish("invalid_proposal", reasons=(str(exc)[:512] or "invalid_bound_inputs",))


def inputs_without_proposal(inputs):
    return {k: v for k, v in inputs.items() if k != "proposal"}


def make_stored_scope_transition_gap(result, *, task_contract, current_context, repository_id):
    """Adapt the already validated question to the frozen OOP UI schema.

    Core/UI consumers must reconstruct this entire payload, not trust its hash.
    No DETECT.2 admission_schema is used: this is a new narrowly owned producer.
    """
    if not isinstance(result, ScopeSemanticRecheck):
        raise TypeError("typed_scope_recheck_required")
    if not result.gap:
        return None
    if (result.repository_id != repository_id or result.source_path != current_context.file
            or result.source_fingerprint != current_context.source_fingerprint
            or result.task_contract_fingerprint != _hash(task_contract.as_dict())):
        raise ValueError("scope_gap_input_binding_mismatch")
    gap = result.gap
    body = dict(gap_kind="oop_intent", scope_recheck_schema=SCHEMA_VERSION,
        dimension=DIMENSION, subdimensions=[DIMENSION], question=gap.question,
        alternatives=[asdict(x) for x in gap.alternatives], evidence_refs=list(gap.evidence_refs),
        current_facts=[dict(kind="existing_savings_transition",
            description="BankAccount.saving(...) currently modifies its ordinary balance.",
            evidence_refs=[r for r in gap.evidence_refs if r.startswith(("saving_declarations:", "current_source:"))],
            provenance="current_source_fact")],
        interpretations=[dict(kind="desired_savings_ownership",
            description="The resolved future design owns savings state and interest behavior on SavingAccount.",
            evidence_refs=[r for r in gap.evidence_refs if r.startswith("effective_design:")],
            provenance="validated_continuation")],
        task_fingerprint=gap.task_fingerprint, task_contract_fingerprint=result.task_contract_fingerprint,
        repository_id=repository_id, source_path=result.source_path, source_fingerprint=result.source_fingerprint,
        class_identity=result.class_identity, proposal_fingerprint=result.proposal_fingerprint,
        effective_design_fingerprint=result.effective_design_fingerprint,
        declaration_fingerprints=list(result.declaration_fingerprints),
        evidence_fingerprint=_hash(sorted(gap.evidence_refs)), scope_authority="proposal_only",
        scope_expansion="deferred")
    body["gap_id"] = _hash(body)
    return body


# Exact complete meanings only. Unknown qualifications never disappear.
_ANSWER_FORMS = {
    "savings_only_on_subclass": (
        "a", "savings_only_on_subclass",
        "Savings functionality should only belong to SavingAccount. BankAccount should no longer have savings behavior in the intended model.",
        "Savings functionality should exist only on SavingAccount. The base BankAccount should no longer expose the current savings behavior as part of the intended design.",
        "Savings functionality should exist only on SavingAccount; base savings behavior should no longer be part of the intended API.",
    ),
    "preserve_base_compatibility": (
        "b", "preserve_base_compatibility",
        "Keep BankAccount's current saving behavior for compatibility, and SavingAccount should have separate savingBalance behavior.",
        "Keep the existing BankAccount saving behavior for compatibility, while SavingAccount has its own savings-state behavior.",
    ),
    "subclass_specialization": (
        "c", "subclass_specialization",
        "Keep a common savings operation concept, but SavingAccount should specialize it to use savingBalance.",
        "Keep a base savings contract but let SavingAccount specialize its behavior to use savingBalance.",
    ),
}


def _normalized(text):
    return re.sub(r"\s+", " ", text.replace("’", "'").strip()).casefold().rstrip(". ")


def _project_answer(answer, design):
    text = answer.text
    span = EvidenceSpan(text[:600], 0, min(len(text), 600))
    inherited = {x.dimension: x.value for x in design.continuation.typed_answer_commitments}
    # Reusing the frozen answer evidence grammar here only detects attempts to
    # contradict preserved commitments. It never revises those dimensions.
    prior = extract_clarification_answer(answer, tuple(inherited), design.base)
    conflicts = list(prior.conflicts)
    for item in prior.commitments:
        if item.dimension in inherited and item.value != inherited[item.dimension]:
            conflicts.append(AnswerConflict("contradicts_preserved_design", (item.evidence,),
                                            ("effective_design:" + design.fingerprint,)))
    if re.search(r"\bsavingbalance\s+(?:(?:should|must)\s+(?:be|belong)\s+|belongs?\s+)(?:on|in|to)\s+bankaccount\b", text, re.I):
        conflicts.append(AnswerConflict("contradicts_subclass_only_state", (span,),
                                       ("effective_design:" + design.fingerprint,)))
    for relationship in design.relationships:
        if re.search(r"\b" + re.escape(relationship.child)
                     + r"\s+(?:(?:should|must)\s+)?(?:not\s+extend|mustn't\s+extend|does\s+not\s+extend)\s+"
                     + re.escape(relationship.parent) + r"\b", text, re.I):
            conflicts.append(AnswerConflict("contradicts_preserved_inheritance", (span,),
                                           ("effective_design:" + design.fingerprint,)))
    if (inherited.get("savings_interest_semantics") == "interest_applies_to_saving_balance"
            and re.search(r"\binterest\s+(?:(?:should|must)\s+)?(?:apply|applies)\s+to\s+"
                          r"(?:(?:the|inherited|ordinary|base)\s+)*balance\b", text, re.I)):
        conflicts.append(AnswerConflict("contradicts_preserved_interest_target", (span,),
                                       ("effective_design:" + design.fingerprint,)))
    if conflicts:
        return (), tuple(conflicts), ()
    normalized = _normalized(text)
    values = [value for value, forms in _ANSWER_FORMS.items() if normalized in {_normalized(x) for x in forms}]
    if len(values) != 1:
        return (), (), (span,)
    return (ScopeTransitionCommitment(values[0], span, answer.answer_fingerprint),), (), ()


def continue_scope_transition(*, stored_transition_gap, stored_transition_answer, previous=None,
                              timings=None, **current_inputs):
    """Append a bound answer, leaving every earlier commitment immutable."""
    started = perf_counter()
    local = {}
    result = recheck_scope_semantics(**current_inputs, timings=local)
    if result.status != "clarification_required":
        raise ValueError("reacquisition_required" if result.status == "reacquisition_required"
                         else "validated_scope_transition_gap_required")
    expected_gap = make_stored_scope_transition_gap(result,
        task_contract=current_inputs["task_contract"], current_context=current_inputs["current_context"],
        repository_id=current_inputs["repository_id"])
    if not isinstance(stored_transition_gap, dict) or _json(stored_transition_gap) != _json(expected_gap):
        raise ValueError("scope_transition_gap_binding_mismatch")
    if not isinstance(stored_transition_answer, dict):
        raise ValueError("scope_transition_answer_binding_mismatch")
    answer = bind_human_answer(expected_gap, stored_transition_answer.get("text", ""))
    if answer.as_dict() != stored_transition_answer:
        raise ValueError("scope_transition_answer_binding_mismatch")
    tick = perf_counter()
    commitments, conflicts, unknown = _project_answer(answer, current_inputs["design_intent"])
    status = ("continuation_conflict" if conflicts else "answer_projection_bounded" if unknown
              else "clarification_projected")
    continuation = ScopeTransitionContinuation(status=status,
        parent_design_fingerprint=result.effective_design_fingerprint,
        parent_continuation_fingerprint=current_inputs["design_intent"].continuation.fingerprint,
        parent_gap_id=expected_gap["gap_id"], proposal_fingerprint=result.proposal_fingerprint,
        task_contract_fingerprint=result.task_contract_fingerprint,
        answer_fingerprint=answer.answer_fingerprint, answer_record_fingerprint=_hash(answer.as_dict()),
        repository_id=result.repository_id, source_path=result.source_path,
        source_fingerprint=result.source_fingerprint, class_identity=result.class_identity,
        declaration_fingerprints=result.declaration_fingerprints,
        typed_answer_commitments=commitments, resolved_dimensions=(DIMENSION,) if commitments else (),
        remaining_dimensions=() if commitments else (DIMENSION,), conflicts=conflicts,
        not_resolved_by_continuation=unknown)
    if previous is not None:
        payload = previous.as_dict() if isinstance(previous, ScopeTransitionContinuation) else previous
        if payload != continuation.as_dict():
            raise ValueError("clarification_conflict")
    if timings is not None:
        timings.update(local, answer_projection_seconds=perf_counter()-tick,
                       total_seconds=perf_counter()-started)
    return continuation


def recheck_refreshed_scope_semantics(*, refreshed_proposal, **current_inputs):
    """Apply RECHECK.1's no-gap gate to a reconstructed REFRESH.1 proposal.

    The adapter verifies P1 against its P0 and semantic parent chain before
    checking that the resolved transition no longer appears as a new human gap.
    It does not admit P1 or change the scope authority contract.
    """
    from core.structural_scope_refresh import recheck_refreshed_scope_semantics as recheck
    return recheck(refreshed_proposal=refreshed_proposal, **current_inputs)
