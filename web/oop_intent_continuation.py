"""Consume the existing OOP session's stored answer; stop at semantic readiness."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import perf_counter

from core.design_intent_continuation import continue_design_intent, compose_effective_design
from core.input_understanding import understand_request
from core.oop_intent_detector import detect_missing_future_design_contract
from core.oop_intent_session import validate_stored_gap
from core.proposed_design_intent import project_proposed_design_intent
from core.repository_identity import derive_repository_id
from web.oop_intent_adapter import _context_from_raw
from web.session_store import find_session, update_oop_intent_wait


def _semantic_payload(value):
    if isinstance(value, dict):
        return {key: _semantic_payload(item) for key, item in value.items()
                if key != "continuation_timings" and not key.endswith("_seconds")}
    if isinstance(value, list):
        return [_semantic_payload(item) for item in value]
    return value


def project_stored_oop_answer(session_id: str) -> dict:
    """No submitted payload can replace stored history or grant authoring.

    Read only the gap's exact source path. Same-answer retries revalidate the
    chain/freshness and reuse its immutable result; no new session is opened.
    """
    started = perf_counter()
    result = {"patch": "", "patch_candidate": None, "patch_plan": None,
              "authority": "read_only", "write_authority": False,
              "execution_authorized": False, "auto_apply": False,
              "repair_scope_authority": False, "patch_author_calls": 0,
              "model_calls": 0, "repository_traversals": 0,
              "usage": {"patch_author_calls": 0},
              "clarification_session_id": session_id}
    safe_result = dict(result)
    session = find_session(session_id)
    if not session or session.get("clarification_kind") != "oop_intent":
        return {**result, "status": "rejected", "code": "wrong_run"}
    try:
        gap = validate_stored_gap(session["oop_intent_gap"],
                                  task_text=session["query"], repo_path=session["repo_path"])
        if gap.get("admission_schema") != "oop_intent_detect_2_v1":
            raise ValueError("wrong_gap")
        answer = session.get("clarification_answer")
        if answer is None:
            raise ValueError("stored_answer_required")
        root = Path(session["repo_path"]).resolve()
        target = (root / gap["source_path"]).resolve()
        target.relative_to(root)
        raw = target.read_bytes()
        if sha256(raw).hexdigest() != gap["source_fingerprint"]:
            raise ValueError("reacquisition_required")
        contract = understand_request(session["query"])
        base = project_proposed_design_intent(contract)
        repository_id = derive_repository_id(root)
        context = _context_from_raw(raw=raw, path=gap["source_path"], design=base,
                                    repository_id=repository_id,
                                    target_symbol=gap["class_identity"])
        timings = {}
        old = session.get("result") or {}
        continuation = continue_design_intent(
            task_contract=contract, base_design=base, stored_gap=gap, stored_answer=answer,
            current_context=context, current_source=raw, repo_path=str(root),
            previous=old.get("design_intent_continuation"), timings=timings)
        effective_start = perf_counter()
        effective = compose_effective_design(base, continuation)
        effective_payload = effective.as_dict()
        timings["effective_projection_seconds"] = perf_counter()-effective_start
        detection_start = perf_counter()
        detection = detect_missing_future_design_contract(
            task_contract=contract, design_intent=effective, current_context=context,
            current_source=raw, repository_id=repository_id,
            stored_gap=gap, stored_answer=answer, repo_path=str(root))
        timings["detection_reentry_seconds"] = perf_counter()-detection_start
        # Recheck the same exact file before publishing a usable result.
        if target.read_bytes() != raw:
            raise ValueError("reacquisition_required")
        timings["total_seconds"] = perf_counter()-started
        messages = {
            "clarification_projected": (detection.gap.question if detection.gap else
                "Clarification projected into typed design evidence. Semantic readiness reached; scope expansion is deferred."),
            "answer_projection_bounded": "The answer contains clauses this bounded continuation cannot resolve.",
            "continuation_conflict": "The answer conflicts with preserved design commitments; no commitment was replaced.",
        }
        result.update(status=continuation.status, answer=messages[continuation.status],
                      clarification_answer=answer,
                      design_intent_continuation=continuation.as_dict(),
                      effective_design_intent=effective_payload,
                      oop_intent_detection=detection.as_dict(),
                      continuation_timings=timings,
                      remaining_gap=detection.as_dict()["possible_intent_gaps"],
                      first_remaining_blocker=("SCOPE_EXPANSION_REQUIRED" if detection.status == "no_gap"
                          else "human_clarification_required" if detection.gap else continuation.status))
        if old.get("design_intent_continuation") is not None:
            if _semantic_payload(old) != _semantic_payload(result):
                raise ValueError("stored_projection_mismatch")
            return old
    except (OSError, KeyError, TypeError, ValueError) as exc:
        code = "reacquisition_required" if isinstance(exc, OSError) else str(exc)
        result = safe_result
        result.update(status="reacquisition_required" if code == "reacquisition_required" else "rejected",
                      code=code, answer="The stored clarification requires validation before semantic readiness.")
        # Keep an existing immutable revision intact even if a retry detects a
        # stale source or a forged stored payload. Do not overwrite its history.
        if (session.get("result") or {}).get("design_intent_continuation") is not None:
            return result
    update_oop_intent_wait(session_id, status=result["status"], result=result)
    return result
