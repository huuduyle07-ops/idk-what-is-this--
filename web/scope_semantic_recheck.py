"""PATCH.SCOPE.RECHECK.1 bridge into the frozen OOP clarification lifecycle.

The stored input capsule preserves typed inputs rather than reparsing the task.
Its closed codec is only transport: the core reconstructs the proposal, gap and
answer chain before any evidence is admitted. Only already bound source paths
are freshness-read; no provider, author, scope admission or traversal is used.
"""
from __future__ import annotations

import base64
from dataclasses import fields, is_dataclass, replace
from hashlib import sha256
import json
import math
from pathlib import Path
from time import perf_counter

from core.oop_intent_session import bind_human_answer, validate_stored_gap
from core.repository_identity import derive_repository_id
from web.session_store import create_oop_intent_wait, find_session, load_sessions, update_oop_intent_wait


RECHECK_SCHEMA = "patch_scope_recheck_1_v1"
CAPSULE_SCHEMA = "scope_recheck_typed_inputs_1_v1"
MAX_CAPSULE_BYTES = 8 * 1024 * 1024
MAX_CODEC_NODES = 50_000
MAX_CODEC_DEPTH = 32
INPUT_KEYS = frozenset({
    "proposal", "task_contract", "design_intent", "semantic_detection",
    "current_context", "current_source", "repository_id", "repo_path",
    "stored_gap", "stored_answer", "current_scope", "expected_scope_fingerprint",
    "related_contexts",
})


def _types():
    """Fixed known records only; stored data cannot select an import or class."""
    from core import authoring_repair_scope as authoring
    from core import behavioral_expectation as behavioral
    from core import class_semantic_context as context
    from core import clarification_answer_evidence as answer
    from core import design_intent_continuation as continuation
    from core import explicit_design_evidence as design_evidence
    from core import explicit_evidence as explicit
    from core import oop_intent_detector as detection
    from core import oop_semantic_review as review
    from core import proposed_design_intent as design
    from core import repair_scope as repair
    from core import structural_scope_expansion as expansion
    from core import task_contract as task

    records = (
        task.RawRequest, task.TaskClassification, task.Subject, task.Relationship,
        task.UserSuppliedFramework, task.RequestedOutput, task.Constraint,
        task.ExecutionRequirements, task.PreservationItem, task.PreservationReport,
        task.TaskContract, behavioral.BehavioralExpectation,
        explicit.ExplicitComparison, explicit.ExplicitFramework,
        explicit.ExplicitConstraint, explicit.ExplicitRequestedOutput, explicit.ExplicitEvidence,
        design_evidence.EvidenceSpan, design_evidence.InheritanceCommitment,
        design_evidence.StateOwnershipCommitment, design_evidence.BehaviorGate,
        design_evidence.ExplicitAbsence, design_evidence.DesignEvidence,
        design.ProposedStateCommitment, design.UnresolvedDesignDimension,
        design.DesignCommitmentConflict, design.ProposedDesignIntent,
        answer.AnswerCommitment, answer.AnswerConflict,
        continuation.DesignIntentContinuation, continuation.EffectiveProposedDesignIntent,
        context.SourceSpan, context.ClassIdentity, context.TargetIdentity,
        context.FieldSemantic, context.ParameterSemantic, context.CallableSemantic,
        context.ClassRelation, context.ClassSemanticContext,
        detection.OOPIntentDimensionAssessment, detection.OOPCurrentDesiredComparison,
        detection.OOPIntentDetection, review.OOPIntentAlternative, review.OOPIntentGap,
        expansion.ScopeEvidence, expansion.StructuralCapability, expansion.StructuralTarget,
        expansion.DeferredStructuralDecision, expansion.CurrentEditScope,
        expansion.StructuralScopeExpansionProposal,
        repair.RepairDiagnostic, repair.RepairMember, repair.RepairScope,
        authoring.AuthoringRepairScope,
    )
    return {record.__module__ + "." + record.__name__: record for record in records}


def _codec(value, *, decode=False):
    registry = _types()
    count = 0

    def visit(item, depth=0):
        nonlocal count
        count += 1
        if count > MAX_CODEC_NODES or depth > MAX_CODEC_DEPTH:
            raise ValueError("scope_recheck_input_bound_exceeded")
        if item is None or type(item) in {str, int, bool}:
            return item
        if type(item) is float and math.isfinite(item):
            return item
        if decode:
            if not isinstance(item, dict) or not isinstance(item.get("type"), str):
                raise ValueError("malformed_scope_recheck_inputs")
            kind = item["type"]
            if kind in {"bytes", "tuple", "list", "mapping"}:
                if set(item) != {"type", "value"}:
                    raise ValueError("malformed_scope_recheck_inputs")
                content = item["value"]
                if kind == "bytes":
                    if not isinstance(content, str):
                        raise ValueError("malformed_scope_recheck_inputs")
                    try:
                        return base64.b64decode(content, validate=True)
                    except (ValueError, TypeError) as exc:
                        raise ValueError("malformed_scope_recheck_inputs") from exc
                if kind == "mapping":
                    if not isinstance(content, dict) or any(not isinstance(k, str) for k in content):
                        raise ValueError("malformed_scope_recheck_inputs")
                    return {k: visit(v, depth + 1) for k, v in content.items()}
                if not isinstance(content, list):
                    raise ValueError("malformed_scope_recheck_inputs")
                values = [visit(v, depth + 1) for v in content]
                return tuple(values) if kind == "tuple" else values
            cls = registry.get(kind)
            if cls is None or set(item) != {"type", "fields"} or not isinstance(item["fields"], dict):
                raise ValueError("malformed_scope_recheck_inputs")
            names = {field.name for field in fields(cls) if field.init}
            if set(item["fields"]) != names:
                raise ValueError("malformed_scope_recheck_inputs")
            try:
                return cls(**{name: visit(value, depth + 1) for name, value in item["fields"].items()})
            except (TypeError, ValueError, AttributeError) as exc:
                raise ValueError("malformed_scope_recheck_inputs") from exc
        if isinstance(item, bytes):
            return {"type": "bytes", "value": base64.b64encode(item).decode("ascii")}
        if isinstance(item, (tuple, list)):
            return {"type": "tuple" if isinstance(item, tuple) else "list",
                    "value": [visit(v, depth + 1) for v in item]}
        if isinstance(item, dict) and all(isinstance(k, str) for k in item):
            return {"type": "mapping", "value": {k: visit(v, depth + 1) for k, v in item.items()}}
        if is_dataclass(item) and not isinstance(item, type):
            kind = type(item).__module__ + "." + type(item).__name__
            if registry.get(kind) is type(item):
                return {"type": kind, "fields": {
                    field.name: visit(getattr(item, field.name), depth + 1)
                    for field in fields(item) if field.init}}
        raise ValueError("unsupported_scope_recheck_input")

    return visit(value)


def _capsule(inputs):
    # DETECT.2 timing samples are not part of its receipt identity.
    detection = inputs["semantic_detection"]
    stable_inputs = {**inputs, "semantic_detection": replace(detection, **{
        field.name: 0.0 for field in fields(detection) if field.name.endswith("_seconds")})}
    value = {"schema_version": CAPSULE_SCHEMA, "inputs": _codec(stable_inputs)}
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_CAPSULE_BYTES:
        raise ValueError("scope_recheck_input_bound_exceeded")
    return value


def _decode_capsule(value):
    if (not isinstance(value, dict) or set(value) != {"schema_version", "inputs"}
            or value.get("schema_version") != CAPSULE_SCHEMA
            or len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_CAPSULE_BYTES):
        raise ValueError("malformed_scope_recheck_inputs")
    inputs = _codec(value["inputs"], decode=True)
    if not isinstance(inputs, dict) or set(inputs) != INPUT_KEYS:
        raise ValueError("malformed_scope_recheck_inputs")
    return inputs


def _fresh_inputs(inputs, *, repo_path, task_text):
    """Read only paths independently bound by preserved exact class contexts."""
    from core.class_semantic_context import MAX_SOURCE_BYTES
    from core.structural_scope_expansion import MAX_CONTEXTS

    root = Path(repo_path).resolve()
    if (Path(inputs["repo_path"]).resolve() != root
            or derive_repository_id(root) != inputs["repository_id"]
            or inputs["task_contract"].raw_request.text != task_text):
        raise ValueError("scope_recheck_input_binding_mismatch")
    pairs = ((inputs["current_context"], inputs["current_source"]), *inputs["related_contexts"])
    if len(pairs) > MAX_CONTEXTS:
        raise ValueError("scope_recheck_input_bound_exceeded")
    bindings = {row[:3] for row in inputs["proposal"].source_bindings}
    acquired = {}
    for context, raw in pairs:
        if (not isinstance(raw, bytes) or len(raw) > MAX_SOURCE_BYTES
                or (context.file, context.class_identity.qualified_name, context.source_fingerprint) not in bindings):
            raise ValueError("reacquisition_required")
        path = (root / context.file).resolve()
        path.relative_to(root)
        if path not in acquired:
            if path.stat().st_size != len(raw):
                raise ValueError("reacquisition_required")
            acquired[path] = path.read_bytes()
        current = acquired[path]
        if (current != raw or sha256(current).hexdigest() != context.source_fingerprint
                or context.repository_id != inputs["repository_id"]):
            raise ValueError("reacquisition_required")
    return acquired


def _safe_result(session_id=None):
    result = {
        "patch": "", "patch_candidate": None, "patch_plan": None, "candidate": None,
        "authority": "read_only", "scope_authority": "proposal_only",
        "write_authority": False, "execution_authorized": False, "auto_apply": False,
        "repair_scope_authority": False, "patch_author_calls": 0, "author_calls": 0,
        "model_calls": 0, "repository_traversals": 0, "scope_delta": 0,
    }
    if session_id is not None:
        result["clarification_session_id"] = session_id
    return result


def _assert_fresh(acquired):
    for path, raw in acquired.items():
        if path.stat().st_size != len(raw) or path.read_bytes() != raw:
            raise ValueError("reacquisition_required")


def _semantic_payload(value):
    if isinstance(value, dict):
        return {key: _semantic_payload(item) for key, item in value.items()
                if key != "scope_recheck_timings" and not key.endswith("_seconds")}
    if isinstance(value, list):
        return [_semantic_payload(item) for item in value]
    return value


def _validate_phase_result(session, recheck):
    result = session.get("result")
    if not isinstance(result, dict):
        raise ValueError("stored_projection_mismatch")
    for key, expected in _safe_result(session["id"]).items():
        actual = result.get(key)
        if type(actual) is not type(expected) or actual != expected:
            raise ValueError("stored_projection_mismatch")
    if session.get("status") == "waiting_for_clarification":
        if (result.get("status") != "waiting_for_clarification"
                or result.get("scope_semantic_recheck") != recheck.as_dict()
                or result.get("answer") != recheck.gap.question
                or result.get("clarification_kind") != "oop_intent"):
            raise ValueError("stored_projection_mismatch")


def validate_scope_transition_wait(session):
    """Reconstruct a waiting question before display; hashes are not authority."""
    from core.scope_semantic_recheck import recheck_scope_semantics, make_stored_scope_transition_gap

    try:
        gap = validate_stored_gap(session["oop_intent_gap"], task_text=session["query"], repo_path=session["repo_path"])
        if gap.get("scope_recheck_schema") != RECHECK_SCHEMA:
            raise ValueError("wrong_gap")
        inputs = _decode_capsule((session.get("result") or {}).get("scope_recheck_inputs"))
        acquired = _fresh_inputs(inputs, repo_path=session["repo_path"], task_text=session["query"])
        recheck = recheck_scope_semantics(**inputs)
        expected = make_stored_scope_transition_gap(
            recheck, task_contract=inputs["task_contract"], current_context=inputs["current_context"],
            repository_id=inputs["repository_id"])
        if expected is None or gap != expected:
            raise ValueError("parent_gap_binding_mismatch")
        _validate_phase_result(session, recheck)
        _assert_fresh(acquired)
        return gap
    except (OSError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise ValueError("malformed_or_stale_scope_transition_wait") from exc


def admit_scope_semantic_recheck_wait(
    *, proposal, task_contract, design_intent, semantic_detection, current_context,
    current_source, repository_id, repo_path, stored_gap=None, stored_answer=None,
    current_scope=None, expected_scope_fingerprint=None, related_contexts=(), web_mode="instant",
):
    """Admit one reconstructed transition gap to OOP.INTENT.UI.1 and stop."""
    from core.scope_semantic_recheck import recheck_scope_semantics, make_stored_scope_transition_gap

    inputs = dict(proposal=proposal, task_contract=task_contract, design_intent=design_intent,
                  semantic_detection=semantic_detection, current_context=current_context,
                  current_source=current_source, repository_id=repository_id, repo_path=str(Path(repo_path).resolve()),
                  stored_gap=stored_gap, stored_answer=stored_answer, current_scope=current_scope,
                  expected_scope_fingerprint=expected_scope_fingerprint, related_contexts=related_contexts)
    result = _safe_result()
    try:
        acquired = _fresh_inputs(inputs, repo_path=repo_path, task_text=task_contract.raw_request.text)
        recheck = recheck_scope_semantics(**inputs)
        result.update(status=recheck.status, scope_semantic_recheck=recheck.as_dict())
        stored = make_stored_scope_transition_gap(
            recheck, task_contract=task_contract, current_context=current_context, repository_id=repository_id)
        if stored is None:
            return result
        _assert_fresh(acquired)
        capsule = _capsule(inputs)
        for existing in load_sessions():
            if (existing.get("clarification_kind") != "oop_intent"
                    or (existing.get("oop_intent_gap") or {}).get("gap_id") != stored["gap_id"]
                    or existing.get("query") != task_contract.raw_request.text
                    or existing.get("repo_path") != inputs["repo_path"]):
                continue
            old = existing.get("result") or {}
            if old.get("scope_recheck_inputs") != capsule:
                raise ValueError("scope_recheck_input_binding_mismatch")
            validate_scope_transition_wait(existing)
            previous = existing.get("clarification_answer")
            if previous is not None:
                return project_stored_scope_transition_answer(
                    existing["id"], answer_text=previous.get("text", ""), gap_id=stored["gap_id"])
            if existing.get("status") not in {"waiting_for_clarification", "clarification_declined"}:
                raise ValueError("stored_projection_mismatch")
            return old
        session_id = create_oop_intent_wait(
            repo_path=repo_path, task_text=task_contract.raw_request.text,
            stored_gap=stored, task_mode="patch", web_mode=web_mode)
        existing = find_session(session_id)
        old = (existing or {}).get("result") or {}
        if old.get("scope_recheck_inputs") is not None and old["scope_recheck_inputs"] != capsule:
            raise ValueError("scope_recheck_input_binding_mismatch")
        result.update(status="waiting_for_clarification", answer=stored["question"],
                      clarification_kind="oop_intent", clarification_session_id=session_id,
                      scope_recheck_inputs=capsule, first_remaining_blocker="human_clarification_required")
        update_oop_intent_wait(session_id, status="waiting_for_clarification", result=result)
        return result
    except (OSError, KeyError, TypeError, ValueError, AttributeError, RecursionError) as exc:
        code = "reacquisition_required" if isinstance(exc, OSError) else str(exc)
        return {**result, "status": "reacquisition_required" if code == "reacquisition_required" else "rejected", "code": code}


def project_stored_scope_transition_answer(session_id, *, answer_text, gap_id, decline=False):
    """Use the stored typed chain; a submitted answer can resolve meaning only."""
    from core.scope_semantic_recheck import (
        recheck_scope_semantics, make_stored_scope_transition_gap,
        continue_scope_transition, compose_scope_transition_design,
    )

    started = perf_counter()
    result = _safe_result(session_id)
    session = find_session(session_id)
    if not session or session.get("clarification_kind") != "oop_intent":
        return {**result, "status": "rejected", "code": "wrong_run"}, 404
    try:
        gap = validate_stored_gap(session["oop_intent_gap"], task_text=session["query"], repo_path=session["repo_path"])
        if gap.get("scope_recheck_schema") != RECHECK_SCHEMA:
            raise ValueError("wrong_gap")
        if gap_id != gap["gap_id"]:
            raise ValueError("wrong_gap")
        old = session.get("result") or {}
        inputs = _decode_capsule(old.get("scope_recheck_inputs"))
        acquired = _fresh_inputs(inputs, repo_path=session["repo_path"], task_text=session["query"])
        recheck_timings = {}
        recheck = recheck_scope_semantics(**inputs, timings=recheck_timings)
        expected = make_stored_scope_transition_gap(
            recheck, task_contract=inputs["task_contract"], current_context=inputs["current_context"],
            repository_id=inputs["repository_id"])
        if expected is None or gap != expected:
            raise ValueError("parent_gap_binding_mismatch")
        _validate_phase_result(session, recheck)
        if decline:
            if session.get("clarification_answer") is not None:
                raise ValueError("clarification_conflict")
            if session.get("status") == "clarification_declined":
                return old
            result.update(status="clarification_declined", answer="Clarification declined; the savings transition remains unresolved.",
                          scope_recheck_inputs=old["scope_recheck_inputs"])
            update_oop_intent_wait(session_id, status=result["status"], result=result)
            return result
        previous_answer = session.get("clarification_answer")
        if previous_answer is None and session.get("status") != "waiting_for_clarification":
            raise ValueError("clarification_not_waiting")
        answer = bind_human_answer(gap, answer_text, previous_answer)
        projection_timings = {}
        continuation = continue_scope_transition(
            **inputs, stored_transition_gap=gap, stored_transition_answer=answer.as_dict(),
            previous=old.get("scope_transition_continuation"), timings=projection_timings)
        effective = compose_scope_transition_design(inputs["design_intent"], continuation)
        post_timings = {}
        post = recheck_scope_semantics(
            **inputs, transition_continuation=continuation,
            stored_transition_gap=gap, stored_transition_answer=answer.as_dict(), timings=post_timings)
        _assert_fresh(acquired)
        messages = {
            "clarification_projected": "Savings transition meaning resolved. A refreshed scope proposal is required; no edits are authorized.",
            "answer_projection_bounded": "This answer does not resolve the bounded savings transition question.",
            "continuation_conflict": "This answer conflicts with preserved design commitments; no commitment was changed.",
        }
        result.update(status=continuation.status, answer=messages[continuation.status],
                      clarification_answer=answer.as_dict(),
                      scope_transition_continuation=continuation.as_dict(),
                      effective_design_intent=effective.as_dict(), scope_semantic_recheck=post.as_dict(),
                      scope_refresh_required=post.scope_refresh_required,
                      scope_recheck_inputs=old["scope_recheck_inputs"],
                      remaining_gap=post.as_dict().get("possible_intent_gaps", []),
                      first_remaining_blocker=("SCOPE_REFRESH_REQUIRED" if post.scope_refresh_required else continuation.status),
                      scope_recheck_timings={"initial_recheck": recheck_timings, "answer_projection": projection_timings,
                                            "post_answer_recheck": post_timings, "total_seconds": perf_counter() - started})
        if previous_answer is not None:
            if _semantic_payload(old) != _semantic_payload(result):
                raise ValueError("stored_projection_mismatch")
            return old
        update_oop_intent_wait(session_id, status=continuation.status, answer=answer.as_dict(), result=result)
        return result
    except (OSError, KeyError, TypeError, ValueError, AttributeError, RecursionError) as exc:
        code = "reacquisition_required" if isinstance(exc, OSError) else str(exc)
        result.update(status="reacquisition_required" if code == "reacquisition_required" else "rejected", code=code)
        return result, (409 if code in {"reacquisition_required", "clarification_conflict", "wrong_gap", "clarification_not_waiting", "stored_projection_mismatch"} else 400)
