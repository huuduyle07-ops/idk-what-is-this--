"""PATCH.SCOPE.APPROVE.1: human evidence for a ceiling, never admitted scope.

All validation uses the caller's bound buffers and frozen REFRESH/RECHECK
reconstruction. The future admission consumer must supply independently stored
human action evidence and fresh inputs; receipt hashes alone confer nothing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from hashlib import sha256
import json
from time import perf_counter

from core.structural_scope_expansion import (
    StructuralCapability, StructuralTarget, DeferredStructuralDecision,
    scope_fingerprint,
)
from core.structural_scope_refresh import (
    RefreshedStructuralScopeExpansionProposal, ScopeRefreshResult,
    validate_structural_scope_refresh_proposal, recheck_refreshed_scope_semantics,
)

PHASE_ID = "PATCH.SCOPE.APPROVE.1"
SCHEMA_VERSION = "patch_scope_approve_1_v1"
DECISIONS = {
    "approve_exact_scope_ceiling": "approved_for_scope_admission",
    "decline_scope_expansion": "scope_approval_declined",
    "request_scope_revision": "scope_revision_requested",
}
TIMING_FIELDS = ("proposal_reconstruction_validation_seconds", "fixpoint_validation_seconds",
                 "presentation_projection_seconds", "receipt_construction_seconds",
                 "receipt_validation_seconds", "total_seconds")
TRANSITION_SUMMARIES = {
    "savings_only_on_subclass": "Savings behavior belongs only to SavingAccount in the intended model. The base savings API transition remains an implementation decision.",
    "preserve_base_compatibility": "BankAccount.saving remains semantically required for compatibility. SavingAccount uses separate savingBalance behavior.",
    "subclass_specialization": "The common base savings contract remains; SavingAccount specializes its behavior to use savingBalance.",
}
EFFECT_NOTE = ("Approval permits only a later scope admission phase to select a subset of this exact ceiling, "
               "consistent with this semantic design. Approval does not write or apply code. "
               "Possible API changes are permitted ceiling targets, never mandatory edits.")


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _timed(timings, key, started):
    if timings is not None:
        for name in TIMING_FIELDS:
            timings.setdefault(name, 0.0)
        timings[key] = perf_counter() - started


@dataclass(frozen=True, slots=True)
class ApprovedScopeCeiling:
    """Typed maximum identities and certainty; deliberately no author renderer."""
    new_logical_targets: tuple[StructuralTarget, ...]
    existing_targets: tuple[StructuralTarget, ...]
    required_capabilities: tuple[StructuralCapability, ...]
    deferred_decisions: tuple[DeferredStructuralDecision, ...]
    source_bindings: tuple[tuple[str, str, str, str], ...]
    blast_radius: tuple[str, ...]

    def as_dict(self):
        return json.loads(_json(asdict(self)))

    @property
    def fingerprint(self):
        return _hash(self.as_dict())


@dataclass(frozen=True, slots=True)
class StructuralScopeReview:
    proposal: RefreshedStructuralScopeExpansionProposal
    ceiling: ApprovedScopeCeiling
    semantic_fixpoint_evidence_fingerprint: str
    presentation_json: str

    @property
    def presentation(self):
        return json.loads(self.presentation_json)

    @property
    def fingerprint(self):
        return _hash(self.presentation)


@dataclass(frozen=True, slots=True)
class HumanScopeDecisionAction:
    """Trusted action boundary data, kept separately from the receipt.

    Only the guarded scope review POST (or synthetic test replay) supplies this
    record. No task, semantic answer, confidence or provider output is accepted.
    """
    decision: str
    proposal_fingerprint: str
    review_fingerprint: str
    provenance: str
    channel: str
    note: str = ""

    def __post_init__(self):
        if (self.decision not in DECISIONS or self.provenance != "explicit_human"
                or self.channel not in {"scope_review_post", "synthetic_human_action"}
                or not _sha(self.proposal_fingerprint) or not _sha(self.review_fingerprint)):
            raise ValueError("explicit_human_scope_action_required")
        if (type(self.note) is not str or len(self.note) > 1000
                or (self.note and self.decision != "request_scope_revision")
                or any(ord(c) < 32 and c not in "\r\n\t" for c in self.note)):
            raise ValueError("invalid_scope_revision_note")
        object.__setattr__(self, "note", self.note.replace("\r\n", "\n").replace("\r", "\n"))

    def as_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {f.name for f in fields(cls)}:
            raise ValueError("explicit_human_scope_action_required")
        return cls(**value)

    @property
    def fingerprint(self):
        return _hash(self.as_dict())


@dataclass(frozen=True, slots=True)
class StructuralScopeApprovalReceipt:
    status: str
    decision: str
    proposal_fingerprint: str
    parent_proposal_fingerprint: str
    effective_design_fingerprint: str
    transition_continuation_fingerprint: str
    task_contract_fingerprint: str
    repository_id: str
    source_bindings: tuple[tuple[str, str, str, str], ...]
    current_scope_fingerprint: str
    current_repair_scope_fingerprint: str
    semantic_fixpoint_evidence_fingerprint: str
    approved_scope_ceiling: ApprovedScopeCeiling
    approved_scope_ceiling_fingerprint: str
    human_decision_evidence: HumanScopeDecisionAction
    human_decision_evidence_fingerprint: str
    review_fingerprint: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    scope_authority: str = field(default="proposal_only", init=False)
    approval_effect: str = field(init=False)
    eligible_for_admission: bool = field(init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)
    repair_scope_delta: int = field(default=0, init=False)
    authoring_scope_delta: int = field(default=0, init=False)
    candidate: None = field(default=None, init=False)
    patch: str = field(default="", init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)

    def __post_init__(self):
        if (self.decision not in DECISIONS or self.status != DECISIONS[self.decision]
                or not isinstance(self.approved_scope_ceiling, ApprovedScopeCeiling)
                or not isinstance(self.human_decision_evidence, HumanScopeDecisionAction)):
            raise ValueError("invalid_scope_approval_receipt")
        for item in fields(self):
            if item.name.endswith("fingerprint") and not _sha(getattr(self, item.name)):
                raise ValueError("invalid_scope_approval_binding")
        if (self.approved_scope_ceiling_fingerprint != self.approved_scope_ceiling.fingerprint
                or self.human_decision_evidence_fingerprint != self.human_decision_evidence.fingerprint
                or self.decision != self.human_decision_evidence.decision
                or self.proposal_fingerprint != self.human_decision_evidence.proposal_fingerprint
                or self.review_fingerprint != self.human_decision_evidence.review_fingerprint):
            raise ValueError("invalid_scope_approval_binding")
        approved = self.decision == "approve_exact_scope_ceiling"
        object.__setattr__(self, "eligible_for_admission", approved)
        object.__setattr__(self, "approval_effect", "eligible_for_admission_only" if approved else "no_admission_eligibility")

    def as_dict(self):
        return json.loads(_json(asdict(self)))

    @property
    def fingerprint(self):
        return _hash(self.as_dict())


def prepare_structural_scope_review(*, proposal, refresh_result, timings=None, **refresh_inputs):
    """Reconstruct exact P1 before display or decision; never trust its flags."""
    started = tick = perf_counter()
    if not isinstance(proposal, RefreshedStructuralScopeExpansionProposal):
        raise ValueError("historical_proposal_not_approvable")
    if (not isinstance(refresh_result, ScopeRefreshResult)
            or refresh_result.structural_semantic_fixpoint is not True
            or refresh_result.status != "refreshed"):
        raise ValueError("approval_unavailable")
    pairs = ((refresh_inputs["current_context"], refresh_inputs["current_source"]),
             *refresh_inputs.get("related_contexts", ()))
    if any(not isinstance(raw, bytes) or sha256(raw).hexdigest() != ctx.source_fingerprint for ctx, raw in pairs):
        raise ValueError("reacquisition_required")
    if (proposal.repository_id != refresh_inputs["repository_id"]
            or proposal.effective_design_fingerprint != refresh_inputs["scope_transition_effective_design"].fingerprint
            or proposal.current_edit_scope.fingerprint != scope_fingerprint(refresh_inputs.get("current_scope"))):
        raise ValueError("approval_stale")
    validate_structural_scope_refresh_proposal(proposal, **refresh_inputs)
    if refresh_result.proposal.as_dict() != proposal.as_dict():
        raise ValueError("wrong_refreshed_proposal")
    _timed(timings, "proposal_reconstruction_validation_seconds", tick)
    tick = perf_counter()
    post = recheck_refreshed_scope_semantics(refreshed_proposal=proposal, **refresh_inputs)
    if (post.status not in {"no_gap", "semantic_recheck_not_required"}
            or post.possible_intent_gaps or post.scope_refresh_required
            or any(x.disposition == "human_owned_material_semantics" for x in post.assessments)
            or post.as_dict() != refresh_result.post_refresh_recheck):
        raise ValueError("approval_unavailable")
    _timed(timings, "fixpoint_validation_seconds", tick)
    tick = perf_counter()
    ceiling = ApprovedScopeCeiling(proposal.new_logical_targets, proposal.existing_targets,
        proposal.required_capabilities, proposal.deferred_decisions, proposal.source_bindings, proposal.blast_radius)
    transition = refresh_inputs["transition_continuation"].typed_answer_commitments[0].value
    presentation = {
        "proposal_fingerprint": proposal.fingerprint,
        "ceiling_fingerprint": ceiling.fingerprint,
        "semantic_fixpoint_evidence_fingerprint": post.fingerprint,
        "transition": transition, "transition_summary": TRANSITION_SUMMARIES[transition],
        "new_logical_structure": [asdict(x) for x in ceiling.new_logical_targets],
        "required_capabilities": [asdict(x) for x in ceiling.required_capabilities],
        "existing_structure": [asdict(x) for x in ceiling.existing_targets],
        "possible_api_changes": [asdict(x) for x in ceiling.existing_targets
                                  if x.category == "MAY_REQUIRE_EXISTING_API_CHANGE"],
        "deferred_implementation": [asdict(x) for x in ceiling.deferred_decisions],
        "blast_radius": list(ceiling.blast_radius), "approval_note": EFFECT_NOTE,
    }
    review = StructuralScopeReview(proposal, ceiling, post.fingerprint, _json(presentation))
    _timed(timings, "presentation_projection_seconds", tick)
    _timed(timings, "total_seconds", started)
    return review


def _construct_receipt(review, action):
    if not isinstance(action, HumanScopeDecisionAction):
        raise ValueError("explicit_human_scope_action_required")
    if (action.proposal_fingerprint != review.proposal.fingerprint
            or action.review_fingerprint != review.fingerprint):
        raise ValueError("scope_approval_binding_mismatch")
    p = review.proposal
    return StructuralScopeApprovalReceipt(DECISIONS[action.decision], action.decision,
        p.fingerprint, p.parent_proposal_fingerprint, p.effective_design_fingerprint,
        p.transition_continuation_fingerprint, p.task_contract_fingerprint, p.repository_id,
        p.source_bindings, p.current_edit_scope.fingerprint, p.current_edit_scope.repair_scope_fingerprint,
        review.semantic_fixpoint_evidence_fingerprint, review.ceiling, review.ceiling.fingerprint,
        action, action.fingerprint, review.fingerprint)


def decide_structural_scope_ceiling(*, human_action, previous_receipt=None, timings=None, **inputs):
    """Append one human decision; retries cannot replace immutable history."""
    started = perf_counter()
    review = prepare_structural_scope_review(**inputs, timings=timings)
    tick = perf_counter()
    receipt = _construct_receipt(review, human_action)
    if previous_receipt is not None:
        previous = previous_receipt.as_dict() if isinstance(previous_receipt, StructuralScopeApprovalReceipt) else previous_receipt
        if not isinstance(previous, dict) or previous.get("decision") != receipt.decision:
            raise ValueError("conflicting_human_scope_decision")
        if _json(previous) != _json(receipt.as_dict()):
            raise ValueError("scope_approval_binding_mismatch")
    _timed(timings, "receipt_construction_seconds", tick)
    _timed(timings, "total_seconds", started)
    return receipt


def validate_structural_scope_approval_receipt(receipt, *, stored_human_action,
        require_eligible=True, conflicting_action=None, timings=None, **inputs):
    """Pure future-admission seam: reconstruct from independent human evidence.

    Callers provide current buffers/scope and the currently selected P1. Any
    supersession or change fails eligibility without rewriting this receipt.
    """
    started = perf_counter()
    review = prepare_structural_scope_review(**inputs)
    expected = _construct_receipt(review, stored_human_action)
    payload = receipt.as_dict() if isinstance(receipt, StructuralScopeApprovalReceipt) else receipt
    if _json(payload) != _json(expected.as_dict()):
        raise ValueError("stale_or_forged_scope_approval_receipt")
    if conflicting_action is not None and conflicting_action != stored_human_action:
        raise ValueError("conflicting_human_scope_decision")
    if require_eligible and not expected.eligible_for_admission:
        raise ValueError("scope_approval_not_eligible")
    _timed(timings, "receipt_validation_seconds", started)
    return expected
