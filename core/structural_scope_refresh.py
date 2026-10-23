"""PATCH.SCOPE.REFRESH.1: re-propose structure after a validated semantic change.

The old EXPAND.1 proposal is reconstructed against its original design and
retained only as historical evidence. A new proposal is planned from the exact
same acquired source plus the validated scope-transition meaning. Nothing here
admits RepairScope, authors code, calls a provider, or traverses a repository.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from hashlib import sha256
import json
from time import perf_counter

from core.design_intent_continuation import (
    EffectiveProposedDesignIntent, DesignIntentContinuation,
    compose_effective_design, validate_effective_design,
)
from core.oop_intent_detector import OOPIntentDetection, detect_missing_future_design_contract
from core.proposed_design_intent import ProposedDesignIntent, project_proposed_design_intent
from core.scope_semantic_recheck import (
    DIMENSION, ScopeSemanticRecheck, ScopeTransitionContinuation,
    ScopeTransitionEffectiveDesign, TransitionAssessment,
    compose_scope_transition_design, recheck_scope_semantics,
)
from core.structural_scope_expansion import (
    StructuralScopeExpansionProposal, StructuralScopeExpansionResult,
    _construct_structural_scope_expansion, detection_fingerprint,
    validate_structural_scope_expansion_proposal,
)
from core.task_contract import TaskContract

PHASE_ID = "PATCH.SCOPE.REFRESH.1"
SCHEMA_VERSION = "patch_scope_refresh_1_v1"
REFRESH_REASON = "semantic_transition_resolved"
TRANSITIONS = frozenset({"savings_only_on_subclass", "preserve_base_compatibility",
                        "subclass_specialization"})
TIMING_FIELDS = ("parent_validation_seconds", "revised_semantic_validation_seconds",
                 "scope_regeneration_seconds", "semantic_diff_seconds",
                 "post_refresh_recheck_seconds", "total_seconds")


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True, slots=True)
class RefreshedStructuralScopeExpansionProposal(StructuralScopeExpansionProposal):
    """An EXPAND-compatible proposal whose semantic revision is explicit."""

    parent_proposal_fingerprint: str
    transition_continuation_fingerprint: str
    refresh_reason: str = REFRESH_REASON
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self):
        StructuralScopeExpansionProposal.__post_init__(self)
        if (not _sha(self.parent_proposal_fingerprint)
                or not _sha(self.transition_continuation_fingerprint)
                or self.refresh_reason != REFRESH_REASON):
            raise ValueError("invalid_scope_refresh_parentage")

    def as_dict(self):
        value = StructuralScopeExpansionProposal.as_dict(self)
        value["phase_id"] = PHASE_ID
        return json.loads(_json(value))


@dataclass(frozen=True, slots=True)
class ScopeRefreshResult:
    status: str
    proposal: RefreshedStructuralScopeExpansionProposal | None = None
    reasons: tuple[str, ...] = ()
    semantic_diff_json: str = "{}"
    post_refresh_recheck_json: str = "{}"
    structural_semantic_fixpoint: bool = False
    performance: tuple[tuple[str, float], ...] = ()
    scope_authority: str = field(default="proposal_only", init=False)
    authority: str = field(default="proposal_only", init=False)
    write_authority: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    candidate: None = field(default=None, init=False)
    patch: str = field(default="", init=False)
    repair_scope_delta: int = field(default=0, init=False)
    authoring_scope_delta: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self):
        if self.status not in {"refreshed", "not_applicable", "semantic_transition_unresolved",
                "reacquisition_required", "invalid_proposal", "scope_evidence_incomplete", "bounded"}:
            raise ValueError("invalid_scope_refresh_status")
        if (self.status == "refreshed") != isinstance(self.proposal, RefreshedStructuralScopeExpansionProposal):
            raise ValueError("invalid_scope_refresh_result")
        if not isinstance(self.reasons, tuple) or len(self.reasons) > 64:
            raise ValueError("invalid_scope_refresh_reasons")
        if not isinstance(self.performance, tuple) or any(
                not isinstance(x, tuple) or len(x) != 2 or x[0] not in TIMING_FIELDS
                or not isinstance(x[1], (int, float)) or x[1] < 0 for x in self.performance):
            raise ValueError("invalid_scope_refresh_performance")
        for payload in (self.semantic_diff_json, self.post_refresh_recheck_json):
            if _json(json.loads(payload)) != payload:
                raise ValueError("invalid_scope_refresh_payload")

    @property
    def first_remaining_blocker(self):
        return "SCOPE_APPROVAL_NOT_IMPLEMENTED" if self.status == "refreshed" else self.status.upper()

    @property
    def semantic_diff(self):
        return json.loads(self.semantic_diff_json)

    @property
    def post_refresh_recheck(self):
        return json.loads(self.post_refresh_recheck_json)

    def as_dict(self):
        return json.loads(_json({**asdict(self), "phase_id": PHASE_ID,
            "first_remaining_blocker": self.first_remaining_blocker,
            "proposal": None if self.proposal is None else self.proposal.as_dict(),
            "semantic_diff": self.semantic_diff,
            "post_refresh_recheck": self.post_refresh_recheck}))


@dataclass(frozen=True, slots=True)
class _RefreshInputs:
    historical_proposal: StructuralScopeExpansionProposal
    task_contract: TaskContract
    original_design_intent: ProposedDesignIntent
    continue1_continuation: DesignIntentContinuation
    original_stored_gap: object
    original_stored_answer: object
    original_semantic_detection: OOPIntentDetection
    transition_continuation: ScopeTransitionContinuation
    scope_transition_effective_design: ScopeTransitionEffectiveDesign
    validated_recheck_receipt: ScopeSemanticRecheck
    stored_transition_gap: object
    stored_transition_answer: object
    current_context: object
    current_source: bytes
    repository_id: str
    repo_path: str
    current_scope: object = None
    expected_scope_fingerprint: str | None = None
    related_contexts: tuple = ()


def _target_map(proposal):
    return {item.target: item for item in (*proposal.existing_targets, *proposal.new_logical_targets)}


def _capability_map(proposal):
    return {(item.code, item.target): item for item in proposal.required_capabilities}


def _semantic_diff(old, new):
    before, after = _target_map(old), _target_map(new)
    old_caps, new_caps = _capability_map(old), _capability_map(new)
    old_deferred = {(x.target, x.decision): x for x in old.deferred_decisions}
    new_deferred = {(x.target, x.decision): x for x in new.deferred_decisions}
    certainty_changes = []
    for key in sorted(old_caps.keys() & new_caps.keys()):
        a, b = old_caps[key], new_caps[key]
        if a.certainty != b.certainty:
            certainty_changes.append({"code": key[0], "target": key[1],
                "from": a.certainty, "to": b.certainty,
                "old_requirement": a.requirement, "new_requirement": b.requirement})
    reason_changes = []
    for key in sorted(before.keys() & after.keys()):
        a, b = before[key], after[key]
        changes = {}
        for field_name in ("reason", "category", "kind", "api_surface"):
            if getattr(a, field_name) != getattr(b, field_name):
                changes[field_name] = {"from": getattr(a, field_name), "to": getattr(b, field_name)}
        if changes:
            reason_changes.append({"target": key, "changes": changes})
    resolved = [{"target": target, "decision": decision, "alternatives": list(item.alternatives)}
                for (target, decision), item in old_deferred.items()
                if decision == DIMENSION and (target, decision) not in new_deferred]
    retained = [{"target": target, "decision": decision, "alternatives": list(item.alternatives)}
                for (target, decision), item in old_deferred.items()
                if (target, decision) in new_deferred and decision != DIMENSION]
    old_radii, new_radii = set(old.blast_radius), set(new.blast_radius)
    return {
        "targets_added": sorted(after.keys() - before.keys()),
        "targets_removed": sorted(before.keys() - after.keys()),
        "target_classification_or_reason_changes": reason_changes,
        "target_certainty_changed": certainty_changes,
        "deferred_decisions_resolved": resolved,
        "deferred_decisions_retained": retained,
        "blast_radius_changes": {"added": sorted(new_radii - old_radii),
                                 "removed": sorted(old_radii - new_radii)},
        "proposal_reason_changes": {"added": sorted(set(new.reasons) - set(old.reasons)),
                                    "removed": sorted(set(old.reasons) - set(new.reasons))},
    }


def _as_refreshed(base, *, parent_fingerprint, continuation_fingerprint):
    values = {item.name: getattr(base, item.name) for item in fields(StructuralScopeExpansionProposal)
              if item.init}
    return RefreshedStructuralScopeExpansionProposal(**values,
        parent_proposal_fingerprint=parent_fingerprint,
        transition_continuation_fingerprint=continuation_fingerprint)


def _result(status, reason, *, proposal=None, diff=None, recheck=None, fixpoint=False, timings=None):
    return ScopeRefreshResult(status=status, proposal=proposal, reasons=tuple(reason),
        semantic_diff_json=_json(diff or {}),
        post_refresh_recheck_json=_json({} if recheck is None else recheck.as_dict()),
        structural_semantic_fixpoint=fixpoint,
        performance=tuple((name, float((timings or {}).get(name, 0.0))) for name in TIMING_FIELDS))


def _check_source_bindings(inputs):
    if not isinstance(inputs.current_source, bytes):
        return False
    digest = sha256(inputs.current_source).hexdigest()
    if (not inputs.current_context or inputs.current_context.source_fingerprint != digest
            or inputs.current_context.repository_id != inputs.repository_id):
        return False
    bindings = {(row[0], row[1], row[2]) for row in inputs.historical_proposal.source_bindings}
    rows = (inputs.current_context, *[pair[0] for pair in inputs.related_contexts])
    return all((ctx.file, ctx.class_identity.qualified_name, ctx.source_fingerprint) in bindings
               for ctx in rows)


def _refresh_core(inputs: _RefreshInputs, timings):
    """Validate both semantic parents and construct exactly one replacement."""
    started = perf_counter()
    timings.update({name: 0.0 for name in TIMING_FIELDS})
    if not isinstance(inputs.task_contract, TaskContract):
        return _result("invalid_proposal", ("typed_task_contract_required",), timings=timings)
    if inputs.task_contract.task.type in {"review", "analysis", "comparative_analysis", "question", "research"}:
        return _result("not_applicable", ("review_only_bank1_has_no_structural_scope",), timings=timings)
    if not isinstance(inputs.historical_proposal, StructuralScopeExpansionProposal):
        return _result("invalid_proposal", ("typed_historical_proposal_required",), timings=timings)
    if not _check_source_bindings(inputs):
        return _result("reacquisition_required", ("current_source_or_context_changed",), timings=timings)

    tick = perf_counter()
    try:
        if (not isinstance(inputs.original_design_intent, ProposedDesignIntent)
                or inputs.original_design_intent.as_dict() != project_proposed_design_intent(inputs.task_contract).as_dict()):
            raise ValueError("original_design_projection_mismatch")
        original_design = compose_effective_design(inputs.original_design_intent,
                                                   inputs.continue1_continuation)
        validate_effective_design(task_contract=inputs.task_contract, design_intent=original_design,
            current_context=inputs.current_context, current_source=inputs.current_source,
            repo_path=inputs.repo_path, stored_gap=inputs.original_stored_gap,
            stored_answer=inputs.original_stored_answer)
        detection = detect_missing_future_design_contract(task_contract=inputs.task_contract,
            design_intent=original_design, current_context=inputs.current_context,
            current_source=inputs.current_source, repository_id=inputs.repository_id,
            stored_gap=inputs.original_stored_gap, stored_answer=inputs.original_stored_answer,
            repo_path=inputs.repo_path)
        if (detection.status != "no_gap" or not isinstance(inputs.original_semantic_detection, OOPIntentDetection)
                or detection_fingerprint(detection) != detection_fingerprint(inputs.original_semantic_detection)):
            raise ValueError("historical_semantic_detection_mismatch")
        validate_structural_scope_expansion_proposal(inputs.historical_proposal,
            task_contract=inputs.task_contract, design_intent=original_design,
            semantic_detection=detection, current_context=inputs.current_context,
            current_source=inputs.current_source, repository_id=inputs.repository_id,
            current_scope=inputs.current_scope,
            expected_scope_fingerprint=inputs.expected_scope_fingerprint,
            related_contexts=inputs.related_contexts)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
        timings["parent_validation_seconds"] = perf_counter() - tick
        reason = str(exc) or "historical_proposal_validation_failed"
        status = "reacquisition_required" if "reacquisition_required" in reason else "invalid_proposal"
        timings["total_seconds"] = perf_counter() - started
        return _result(status, (reason[:512],), timings=timings)
    timings["parent_validation_seconds"] = perf_counter() - tick

    tick = perf_counter()
    try:
        if not isinstance(inputs.transition_continuation, ScopeTransitionContinuation):
            raise ValueError("typed_transition_continuation_required")
        effective = compose_scope_transition_design(original_design, inputs.transition_continuation)
        if (not isinstance(inputs.scope_transition_effective_design, ScopeTransitionEffectiveDesign)
                or inputs.scope_transition_effective_design.as_dict() != effective.as_dict()
                or effective.fingerprint != inputs.scope_transition_effective_design.fingerprint):
            raise ValueError("forged_scope_transition_effective_design")
        if (not isinstance(inputs.validated_recheck_receipt, ScopeSemanticRecheck)
                or inputs.validated_recheck_receipt.status != "no_gap"
                or not inputs.validated_recheck_receipt.scope_refresh_required):
            return _result("semantic_transition_unresolved", ("validated_recheck_no_gap_receipt_required",), timings=timings)
        checked = recheck_scope_semantics(
            proposal=inputs.historical_proposal, task_contract=inputs.task_contract,
            design_intent=original_design, semantic_detection=detection,
            current_context=inputs.current_context, current_source=inputs.current_source,
            repository_id=inputs.repository_id, repo_path=inputs.repo_path,
            stored_gap=inputs.original_stored_gap, stored_answer=inputs.original_stored_answer,
            current_scope=inputs.current_scope, expected_scope_fingerprint=inputs.expected_scope_fingerprint,
            related_contexts=inputs.related_contexts,
            transition_continuation=inputs.transition_continuation,
            stored_transition_gap=inputs.stored_transition_gap,
            stored_transition_answer=inputs.stored_transition_answer)
        if (checked.as_dict() != inputs.validated_recheck_receipt.as_dict()
                or checked.status != "no_gap" or not checked.scope_refresh_required
                or checked.effective_design_fingerprint != effective.fingerprint
                or checked.transition_continuation_fingerprint != inputs.transition_continuation.fingerprint):
            raise ValueError("scope_recheck_receipt_mismatch")
        transition_values = {item.dimension: item.value
            for item in inputs.transition_continuation.typed_answer_commitments}
        transition_value = transition_values.get(DIMENSION)
        if (inputs.transition_continuation.status != "clarification_projected"
                or transition_value not in TRANSITIONS
                or inputs.transition_continuation.parent_design_fingerprint != original_design.fingerprint
                or inputs.transition_continuation.parent_continuation_fingerprint != original_design.continuation.fingerprint
                or inputs.transition_continuation.proposal_fingerprint != inputs.historical_proposal.fingerprint
                or inputs.transition_continuation.repository_id != inputs.repository_id
                or inputs.transition_continuation.source_path != inputs.current_context.file
                or inputs.transition_continuation.source_fingerprint != inputs.current_context.source_fingerprint):
            return _result("semantic_transition_unresolved", ("resolved_transition_bound_to_historical_proposal_required",), timings=timings)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
        timings["revised_semantic_validation_seconds"] = perf_counter() - tick
        reason = str(exc) or "revised_semantic_validation_failed"
        status = "reacquisition_required" if "reacquisition_required" in reason else "invalid_proposal"
        timings["total_seconds"] = perf_counter() - started
        return _result(status, (reason[:512],), timings=timings)
    timings["revised_semantic_validation_seconds"] = perf_counter() - tick

    tick = perf_counter()
    planned = _construct_structural_scope_expansion(
        task_contract=inputs.task_contract, design_intent=original_design,
        semantic_detection=detection, current_context=inputs.current_context,
        current_source=inputs.current_source, repository_id=inputs.repository_id,
        current_scope=inputs.current_scope,
        expected_scope_fingerprint=inputs.expected_scope_fingerprint,
        related_contexts=inputs.related_contexts, _transition_value=transition_value,
        _transition_continuation_fingerprint=inputs.transition_continuation.fingerprint,
        _refreshed_effective_design_fingerprint=effective.fingerprint)
    timings["scope_regeneration_seconds"] = perf_counter() - tick
    if planned.proposal is None:
        timings["total_seconds"] = perf_counter() - started
        return _result(planned.status, planned.reasons or ("scope_regeneration_failed",), timings=timings)
    refreshed = _as_refreshed(planned.proposal,
        parent_fingerprint=inputs.historical_proposal.fingerprint,
        continuation_fingerprint=inputs.transition_continuation.fingerprint)
    if (refreshed.effective_design_fingerprint != effective.fingerprint
            or refreshed.repository_id != inputs.repository_id
            or refreshed.source_bindings != inputs.historical_proposal.source_bindings):
        timings["total_seconds"] = perf_counter() - started
        return _result("reacquisition_required", ("refreshed_parent_source_binding_mismatch",), timings=timings)
    timings["total_seconds"] = perf_counter() - started
    return _result("refreshed", ("fresh_proposal_bound_to_resolved_semantics",),
                   proposal=refreshed, timings=timings)


def _post_recheck(proposal, inputs, *, receipt):
    values = {(item.code, item.target): item for item in proposal.required_capabilities}
    transition = values.get((DIMENSION, "BankAccount::saving"))
    unresolved_capabilities = [item.target for item in proposal.required_capabilities
                               if item.certainty == "NEEDS_TRANSITION_DECISION"]
    unresolved_decisions = [item.target + ":" + item.decision for item in proposal.deferred_decisions
                            if item.semantic_recheck_if_behavior_changes]
    if unresolved_capabilities or unresolved_decisions:
        raise ValueError("new_human_semantic_gap_discovered:" + ",".join(
            sorted(set(unresolved_capabilities + unresolved_decisions))))
    target = _target_map(proposal).get("BankAccount::saving")
    selected = inputs.transition_continuation.typed_answer_commitments[0].value
    expected_reason = {
        "savings_only_on_subclass": "base_savings_behavior_must_leave_intended_api",
        "preserve_base_compatibility": "legacy_base_savings_behavior_is_semantically_preserved",
        "subclass_specialization": "base_savings_contract_supports_subclass_specialization",
    }[selected]
    if (transition is None or transition.certainty == "NEEDS_TRANSITION_DECISION"
            or target is None or target.reason != expected_reason
            or any(x.decision == DIMENSION and x.semantic_recheck_if_behavior_changes
                   for x in proposal.deferred_decisions)):
        raise ValueError("refreshed_scope_has_unresolved_semantic_transition")
    if (proposal.parent_proposal_fingerprint != inputs.historical_proposal.fingerprint
            or proposal.transition_continuation_fingerprint != inputs.transition_continuation.fingerprint
            or proposal.effective_design_fingerprint != inputs.scope_transition_effective_design.fingerprint
            or receipt.status != "no_gap" or receipt.effective_design_fingerprint != proposal.effective_design_fingerprint):
        raise ValueError("refreshed_scope_parentage_mismatch")
    return ScopeSemanticRecheck(status="semantic_recheck_not_required",
        proposal_fingerprint=proposal.fingerprint,
        effective_design_fingerprint=proposal.effective_design_fingerprint,
        task_contract_fingerprint=proposal.task_contract_fingerprint,
        repository_id=proposal.repository_id,
        source_fingerprint=inputs.current_context.source_fingerprint,
        source_path=inputs.current_context.file,
        class_identity=inputs.current_context.class_identity.qualified_name,
        assessments=(TransitionAssessment("BankAccount::saving", DIMENSION, "resolved",
            "refreshed_target_carries_validated_human_transition"),),
        reasons=("no_unresolved_human_transition_in_refreshed_proposal",),
        scope_refresh_required=False,
        transition_continuation_fingerprint=inputs.transition_continuation.fingerprint)


def _coerce_inputs(**kwargs):
    try:
        return _RefreshInputs(**kwargs)
    except TypeError as exc:
        raise ValueError("scope_refresh_inputs_incomplete") from exc


def refresh_structural_scope_proposal(*, timings=None, **kwargs):
    """Validate P0 and both semantic chains, then return immutable proposal P1."""
    local = {}
    inputs = _coerce_inputs(**kwargs)
    result = _refresh_core(inputs, local)
    if result.status != "refreshed":
        if timings is not None:
            timings.update(local)
        return result
    tick = perf_counter()
    try:
        # Reconstruct P1 once more through the RECHECK.1 adapter before
        # declaring the semantic/structural fixpoint.
        post_timings = {}
        post = recheck_refreshed_scope_semantics(
            refreshed_proposal=result.proposal, timings=post_timings, **kwargs)
        local["post_refresh_recheck_seconds"] = post_timings.get(
            "post_refresh_recheck_seconds", perf_counter() - tick)
        local["total_seconds"] = local.get("total_seconds", 0.0) + local["post_refresh_recheck_seconds"]
        diff_tick = perf_counter()
        diff = _semantic_diff(inputs.historical_proposal, result.proposal)
        local["semantic_diff_seconds"] = perf_counter() - diff_tick
        local["total_seconds"] += local["semantic_diff_seconds"]
        if timings is not None:
            timings.update(local)
        return replace(result, semantic_diff_json=_json(diff),
            post_refresh_recheck_json=_json(post.as_dict()), structural_semantic_fixpoint=True,
            performance=tuple((name, float(local.get(name, 0.0))) for name in TIMING_FIELDS))
    except (ValueError, TypeError, AttributeError, IndexError) as exc:
        local["post_refresh_recheck_seconds"] = perf_counter() - tick
        local["total_seconds"] = local.get("total_seconds", 0.0) + local["post_refresh_recheck_seconds"]
        if timings is not None:
            timings.update(local)
        reason = str(exc) or "post_refresh_recheck_failed"
        status = "semantic_transition_unresolved" if reason.startswith("new_human_semantic_gap_discovered") else "invalid_proposal"
        return _result(status, (reason,), timings=local)


def validate_structural_scope_refresh_proposal(proposal, **kwargs):
    """Reconstruct a refreshed proposal; fingerprints never confer authority."""
    if not isinstance(proposal, RefreshedStructuralScopeExpansionProposal):
        raise ValueError("typed_scope_refresh_proposal_required")
    inputs = _coerce_inputs(**kwargs)
    rebuilt = _refresh_core(inputs, {})
    if (rebuilt.status != "refreshed" or rebuilt.proposal.as_dict() != proposal.as_dict()):
        raise ValueError("stale_or_forged_scope_refresh_proposal")
    return proposal


def recheck_refreshed_scope_semantics(*, refreshed_proposal, timings=None, **kwargs):
    """Reconstruct P1 from its P0 parent and verify the frozen RECHECK.1 fixpoint."""
    if not isinstance(refreshed_proposal, RefreshedStructuralScopeExpansionProposal):
        raise ValueError("typed_scope_refresh_proposal_required")
    inputs = _coerce_inputs(**kwargs)
    started = perf_counter()
    local = {}
    rebuilt = _refresh_core(inputs, local)
    if (rebuilt.status != "refreshed" or rebuilt.proposal.as_dict() != refreshed_proposal.as_dict()):
        raise ValueError("refreshed_proposal_reconstruction_mismatch")
    result = _post_recheck(refreshed_proposal, inputs,
                           receipt=inputs.validated_recheck_receipt)
    if timings is not None:
        local["post_refresh_recheck_seconds"] = perf_counter() - started
        local["total_seconds"] = local["post_refresh_recheck_seconds"]
        timings.update(local)
    return result
