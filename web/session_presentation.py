"""Read-only view data for persisted web sessions."""
from __future__ import annotations

from typing import Any, Mapping


class CorruptWaitingSession(ValueError):
    """A waiting session lacks the clarification needed for presentation."""


def project_session(session: Mapping[str, Any]) -> dict[str, Any]:
    """Keep session identity and clarification metadata out of the result payload."""
    result = session.get("result")
    if not isinstance(result, dict):
        result = {}
    status = session.get("status") or result.get("status")
    clarification = None
    kind = None
    if status == "waiting_for_clarification":
        if result.get("patch"):
            raise CorruptWaitingSession("Stored waiting session contains a patch candidate.")
        kind = session.get("clarification_kind", "repair_intent")
        if kind == "oop_intent":
            from core.oop_intent_session import validate_stored_gap
            try:
                gap = validate_stored_gap(
                    session.get("oop_intent_gap"),
                    task_text=session.get("query"), repo_path=session.get("repo_path"))
                if (gap.get("scope_recheck_schema") is not None
                        or gap.get("dimension") == "existing_savings_transition"
                        or result.get("scope_recheck_inputs") is not None):
                    from web.scope_semantic_recheck import validate_scope_transition_wait
                    gap = validate_scope_transition_wait(session)
            except (TypeError, ValueError) as exc:
                raise CorruptWaitingSession("Stored OOP clarification is malformed.") from exc
        elif kind == "repair_intent":
            gap = session.get("repair_intent_gap")
        else:
            raise CorruptWaitingSession("Stored clarification kind is unknown.")
        if not isinstance(gap, dict) or not isinstance(gap.get("question"), str) or not gap["question"].strip():
            raise CorruptWaitingSession("Stored waiting session is missing its clarification question.")
        session_id = session.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise CorruptWaitingSession("Stored waiting session is missing its session ID.")
        raw_alternatives = gap.get("alternatives")
        alternatives = tuple(
            item["description"] for item in raw_alternatives
            if isinstance(item, dict) and isinstance(item.get("description"), str)
        ) if isinstance(raw_alternatives, list) else ()
        clarification = {
            "session_id": session_id,
            "question": gap["question"],
            "alternatives": alternatives,
        }
        if kind == "oop_intent":
            clarification.update({
                "kind": kind,
                "gap_id": gap["gap_id"],
                "current_facts": tuple(x["description"] for x in gap["current_facts"]),
                "interpretations": tuple(x["description"] for x in gap["interpretations"]),
                "answer_state": "waiting",
                "action_available": False,
                "task_mode": session.get("task_mode", "review"),
            })
    # PATCH.SCOPE.APPROVE.1 presentation boundary.
    scope_approval = None
    if result.get("scope_approval_inputs") is not None:
        from web.structural_scope_approval import project_scope_approval_session
        try:
            scope_approval = project_scope_approval_session(session)
        except (OSError, ValueError) as exc:
            if isinstance(exc, OSError) or str(exc) in {"reacquisition_required", "approval_stale", "scope_recheck_input_binding_mismatch"}:
                scope_approval = {"summary": None, "status": status, "decision_available": False,
                    "unavailable_reason": "This review is stale. Reacquire the proposal before any later admission. Historical decisions remain recorded."}
            else:
                raise CorruptWaitingSession("Stored scope approval is malformed.") from exc
        except (KeyError, TypeError, AttributeError, RecursionError) as exc:
            raise CorruptWaitingSession("Stored scope approval is malformed.") from exc
    # End PATCH.SCOPE.APPROVE.1 presentation boundary.
    return {
        "session_id": session.get("id"),
        "status": status,
        "clarification_kind": kind,
        "answer": result.get("answer"),
        "patch": result.get("patch"),
        "clarification": clarification,
        "scope_approval": scope_approval,
    }
