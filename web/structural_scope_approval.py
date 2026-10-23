"""Bound scope review/decision in the existing durable session history.

Only the guarded POST creates human evidence. GET projection reconstructs the
stored proposal and checks exact bound files without changing session state.
"""
from __future__ import annotations

from dataclasses import fields
import json
from threading import RLock

from core.design_intent_continuation import compose_effective_design
from core.scope_semantic_recheck import (
    continue_scope_transition, compose_scope_transition_design, recheck_scope_semantics,
)
from core.structural_scope_expansion import (
    StructuralTarget, StructuralCapability, DeferredStructuralDecision, ScopeEvidence,
    scope_fingerprint,
)
from core.structural_scope_refresh import RefreshedStructuralScopeExpansionProposal, ScopeRefreshResult
from core.structural_scope_approval import (
    SCHEMA_VERSION, HumanScopeDecisionAction, prepare_structural_scope_review,
    decide_structural_scope_ceiling, validate_structural_scope_approval_receipt, _json,
)
from web.scope_semantic_recheck import (
    _capsule, _decode_capsule, _fresh_inputs, _assert_fresh, MAX_CAPSULE_BYTES,
)
from web import session_store

_DECISION_LOCK = RLock()


def _parent_inputs(inputs):
    return dict(proposal=inputs["historical_proposal"], task_contract=inputs["task_contract"],
        design_intent=compose_effective_design(inputs["original_design_intent"], inputs["continue1_continuation"]),
        semantic_detection=inputs["original_semantic_detection"], current_context=inputs["current_context"],
        current_source=inputs["current_source"], repository_id=inputs["repository_id"], repo_path=inputs["repo_path"],
        stored_gap=inputs["original_stored_gap"], stored_answer=inputs["original_stored_answer"],
        current_scope=inputs.get("current_scope"), expected_scope_fingerprint=inputs.get("expected_scope_fingerprint"),
        related_contexts=inputs.get("related_contexts", ()))


def _state(proposal):
    return {"proposal_fingerprint": proposal.fingerprint,
            "effective_design_fingerprint": proposal.effective_design_fingerprint,
            "repository_id": proposal.repository_id,
            "current_scope_fingerprint": proposal.current_edit_scope.fingerprint}


def _semantic_state(session):
    result = session.get("result") or {}
    return {"clarification_answer": session.get("clarification_answer"),
        "oop_intent_gap": session.get("oop_intent_gap"),
        **{key: result.get(key) for key in ("effective_design_intent", "design_intent_continuation",
            "scope_transition_continuation", "scope_semantic_recheck", "scope_recheck_inputs")}}


def _transport(proposal, refresh_result, inputs):
    value = {"schema_version": SCHEMA_VERSION, "parent_inputs": _capsule(_parent_inputs(inputs)),
        "transition_gap": inputs["stored_transition_gap"], "transition_answer": inputs["stored_transition_answer"],
        "proposal": proposal.as_dict(), "post_refresh_recheck": refresh_result.post_refresh_recheck,
        "structural_semantic_fixpoint": refresh_result.structural_semantic_fixpoint}
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_CAPSULE_BYTES:
        raise ValueError("scope_approval_inputs_bound_exceeded")
    return value


def _record(cls, value, tuple_fields=()):
    if not isinstance(value, dict) or set(value) != {f.name for f in fields(cls) if f.init}:
        raise ValueError("malformed_scope_approval_inputs")
    return cls(**{k: tuple(v) if k in tuple_fields and v is not None else v for k, v in value.items()})


def _decode(session):
    value = (session.get("result") or {}).get("scope_approval_inputs")
    keys = {"schema_version", "parent_inputs", "transition_gap", "transition_answer", "proposal",
            "post_refresh_recheck", "structural_semantic_fixpoint"}
    if (not isinstance(value, dict) or set(value) != keys or value.get("schema_version") != SCHEMA_VERSION
            or len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_CAPSULE_BYTES):
        raise ValueError("malformed_scope_approval_inputs")
    base = _decode_capsule(value["parent_inputs"])
    acquired = _fresh_inputs(base, repo_path=session["repo_path"], task_text=session["query"])
    continuation = continue_scope_transition(**base,
        stored_transition_gap=value["transition_gap"], stored_transition_answer=value["transition_answer"])
    effective = compose_scope_transition_design(base["design_intent"], continuation)
    recheck = recheck_scope_semantics(**base, transition_continuation=continuation,
        stored_transition_gap=value["transition_gap"], stored_transition_answer=value["transition_answer"])
    inputs = dict(historical_proposal=base["proposal"], task_contract=base["task_contract"],
        original_design_intent=base["design_intent"].base, continue1_continuation=base["design_intent"].continuation,
        original_stored_gap=base["stored_gap"], original_stored_answer=base["stored_answer"],
        original_semantic_detection=base["semantic_detection"], transition_continuation=continuation,
        scope_transition_effective_design=effective, validated_recheck_receipt=recheck,
        stored_transition_gap=value["transition_gap"], stored_transition_answer=value["transition_answer"],
        **{k: base[k] for k in ("current_context", "current_source", "repository_id", "repo_path",
                               "current_scope", "expected_scope_fingerprint", "related_contexts")})
    payload = value["proposal"]
    # Closed records only; no imports, class names or arbitrary fields from storage.
    proposal_values = {f.name: payload[f.name] for f in fields(RefreshedStructuralScopeExpansionProposal) if f.init}
    proposal_values["current_edit_scope"] = base["proposal"].current_edit_scope
    for name in ("existing_targets", "new_logical_targets"):
        proposal_values[name] = tuple(_record(StructuralTarget, x, ("evidence_refs", "member_span")) for x in payload[name])
    proposal_values["required_capabilities"] = tuple(_record(StructuralCapability, x, ("evidence_refs",))
                                                     for x in payload["required_capabilities"])
    proposal_values["deferred_decisions"] = tuple(_record(DeferredStructuralDecision, x, ("alternatives",))
                                                 for x in payload["deferred_decisions"])
    proposal_values["evidence"] = tuple(_record(ScopeEvidence, x) for x in payload["evidence"])
    proposal_values["source_bindings"] = tuple(tuple(x) for x in payload["source_bindings"])
    for name in ("reasons", "blast_radius"):
        proposal_values[name] = tuple(payload[name])
    proposal = RefreshedStructuralScopeExpansionProposal(**proposal_values)
    if _json(proposal.as_dict()) != _json(payload):
        raise ValueError("forged_scope_approval_proposal")
    result = ScopeRefreshResult(status="refreshed", proposal=proposal,
        structural_semantic_fixpoint=value["structural_semantic_fixpoint"],
        post_refresh_recheck_json=json.dumps(value["post_refresh_recheck"], sort_keys=True,
                                            ensure_ascii=False, separators=(",", ":")))
    if (session.get("scope_approval_current_binding") != _state(proposal)
            or _json(session.get("control")) != _json(session.get("scope_approval_control_baseline"))
            or _json(_semantic_state(session)) != _json(session.get("scope_approval_semantic_baseline"))):
        raise ValueError("approval_stale")
    return dict(proposal=proposal, refresh_result=result, **inputs), acquired


def project_scope_approval_session(session):
    """Read-only history, including historical decisions after freshness loss."""
    inputs, acquired = _decode(session)
    review = prepare_structural_scope_review(**inputs)
    result = session["result"]
    if (_json(result.get("scope_approval_review")) != _json(review.presentation)
            or result.get("review_fingerprint") != review.fingerprint):
        raise ValueError("scope_approval_review_binding_mismatch")
    if result.get("status") != session.get("status"):
        raise ValueError("scope_approval_history_mismatch")
    receipt = result.get("scope_approval_receipt")
    if receipt is not None:
        action = HumanScopeDecisionAction.from_dict(session.get("scope_approval_human_action"))
        validated = validate_structural_scope_approval_receipt(receipt, stored_human_action=action,
                                                              require_eligible=False, **inputs)
        if session.get("status") != receipt["status"]:
            raise ValueError("scope_approval_history_mismatch")
    elif session.get("status") != "scope_proposal_awaiting_approval" or session.get("scope_approval_human_action") is not None:
        raise ValueError("scope_approval_history_mismatch")
    for key, expected in _safe_result().items():
        if result.get(key) != expected or type(result.get(key)) is not type(expected):
            raise ValueError("scope_approval_authority_mismatch")
    _assert_fresh(acquired)
    return {"summary": review.presentation, "review_fingerprint": review.fingerprint,
            "proposal_fingerprint": review.proposal.fingerprint, "status": session["status"],
            "decision_available": receipt is None,
            "receipt_fingerprint": None if receipt is None else validated.fingerprint}


def _safe_result():
    return {"patch": "", "candidate": None, "patch_candidate": None, "patch_plan": None,
        "scope_authority": "proposal_only", "write_authority": False, "execution_authorized": False,
        "auto_apply": False, "apply_authority": False, "repair_scope_authority": False,
        "repair_scope_delta": 0, "authoring_scope_delta": 0, "author_calls": 0,
        "model_calls": 0, "repository_traversals": 0}


def register_scope_approval_review(*, proposal, refresh_result, session_id=None, **inputs):
    """Harness seam: store a validated P1 review; registration cannot approve.

    An existing semantic session may be supplied explicitly. This phase never
    discovers or consumes any real session on its own.
    """
    with _DECISION_LOCK:
        review = prepare_structural_scope_review(proposal=proposal, refresh_result=refresh_result, **inputs)
        parent = _parent_inputs(inputs)
        acquired = _fresh_inputs(parent, repo_path=inputs["repo_path"], task_text=inputs["task_contract"].raw_request.text)
        capsule = _transport(proposal, refresh_result, inputs)
        sessions = session_store.load_sessions()
        existing = next((s for s in sessions if s.get("id") == session_id), None) if session_id else next(
            (s for s in sessions if s.get("mode") == "scope_approval" and
             (s.get("scope_approval_current_binding") or {}).get("proposal_fingerprint") == proposal.fingerprint), None)
        if session_id and existing is None:
            raise ValueError("wrong_scope_approval_session")
        if existing and (existing.get("result") or {}).get("scope_approval_inputs") is not None:
            if existing["result"]["scope_approval_inputs"] != capsule:
                raise ValueError("scope_approval_binding_mismatch")
            project_scope_approval_session(existing)
            return existing["id"]
        if existing:
            if existing["query"] != inputs["task_contract"].raw_request.text or existing["repo_path"] != inputs["repo_path"]:
                raise ValueError("scope_approval_binding_mismatch")
        else:
            existing = {"id": "scope-approval-" + proposal.fingerprint, "mode": "scope_approval",
                "title": "Structural scope review", "query": inputs["task_contract"].raw_request.text,
                "repo_path": inputs["repo_path"], "web_mode": "instant", "events": []}
            sessions.insert(0, existing)
        # Preserve the preceding semantic chain when attaching to a known session.
        old = existing.get("result") or {}
        existing.update(status="scope_proposal_awaiting_approval",
            scope_approval_current_binding=_state(proposal),
            scope_approval_control_baseline=existing.get("control"),
            scope_approval_semantic_baseline=_semantic_state(existing))
        existing["events"].append("scope_proposal_awaiting_approval")
        existing["result"] = {**old, **_safe_result(), "status": existing["status"],
            "answer": "Review the exact structural ceiling. No code changes are authorized.",
            "scope_approval_inputs": capsule, "scope_approval_review": review.presentation,
            "review_fingerprint": review.fingerprint, "scope_approval_receipt": None,
            "first_remaining_blocker": "HUMAN_SCOPE_APPROVAL_REQUIRED"}
        _assert_fresh(acquired)
        session_store.save_sessions(sessions[:30])
        return existing["id"]


def submit_scope_approval_decision(session_id, *, proposal_fingerprint, review_fingerprint, decision, note=""):
    """Called only by the guarded human POST; immutable retries are serialized."""
    with _DECISION_LOCK:
        sessions = session_store.load_sessions()
        session = next((s for s in sessions if s.get("id") == session_id), None)
        if session is None or (session.get("result") or {}).get("scope_approval_inputs") is None:
            raise ValueError("wrong_scope_approval_session")
        project_scope_approval_session(session)
        inputs, acquired = _decode(session)
        action = HumanScopeDecisionAction(decision, proposal_fingerprint, review_fingerprint,
                                         "explicit_human", "scope_review_post", note)
        old = session["result"]
        receipt = decide_structural_scope_ceiling(human_action=action,
            previous_receipt=old.get("scope_approval_receipt"), **inputs)
        validate_structural_scope_approval_receipt(receipt, stored_human_action=action,
                                                 require_eligible=False, **inputs)
        _assert_fresh(acquired)
        if old.get("scope_approval_receipt") is not None:
            return old
        session["scope_approval_human_action"] = action.as_dict()
        session["status"] = receipt.status
        session["events"].append(receipt.status)
        message = {"approved_for_scope_admission": "Exact ceiling approved for later admission. No code was changed.",
            "scope_approval_declined": "Scope expansion declined. No code was changed.",
            "scope_revision_requested": "Scope revision requested. The note was recorded; no design or code was changed."}
        session["result"] = {**old, "status": receipt.status, "answer": message[receipt.status],
            "scope_approval_receipt": receipt.as_dict(), "scope_approval_receipt_fingerprint": receipt.fingerprint,
            "first_remaining_blocker": "SCOPE_ADMISSION_NOT_IMPLEMENTED" if receipt.eligible_for_admission else receipt.status.upper()}
        session_store.save_sessions(sessions)
        return session["result"]
