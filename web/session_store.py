from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

SESSION_FILE = Path(__file__).parent / "sessions.json"


def load_sessions() -> list[dict]:
    if not SESSION_FILE.exists():
        return []
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_sessions(sessions: list[dict]) -> None:
    SESSION_FILE.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def find_session(session_id: str) -> dict | None:
    for s in load_sessions():
        if s.get("id") == session_id:
            return s
    return None


def create_repair_intent_wait(*, repo_path: str, task_text: str,
                              control: dict, gap: dict,
                              author_escalation_receipt: dict | None = None) -> str:
    """Persist one waiting Generate continuation in the existing session history."""
    from core.repair_intent import RepairIntentGap, render_question

    resolved_repo = str(Path(repo_path).resolve())
    sessions = load_sessions()
    for existing in sessions:
        if (existing.get("mode") == "repair_intent"
                and existing.get("status") == "waiting_for_clarification"
                and existing.get("query") == task_text
                and existing.get("repo_path") == resolved_repo
                and (existing.get("repair_intent_gap") or {}).get("ambiguity_id")
                    == gap.get("ambiguity_id")):
            return existing["id"]
    session_id = "repair-intent-" + uuid.uuid4().hex
    question = render_question(RepairIntentGap.from_dict(gap))
    waiting = {
        "id": session_id, "title": task_text[:40] or "Repair clarification",
        "query": task_text, "repo_path": resolved_repo,
        "mode": "repair_intent", "web_mode": "instant",
        "status": "waiting_for_clarification", "control": control,
        "repair_intent_gap": gap, "clarification_answer": None,
        "events": ["waiting_for_clarification"],
        "result": {"answer": question, "patch": "",
                   "status": "waiting_for_clarification"},
    }
    if author_escalation_receipt is not None:
        waiting["author_escalation_receipt"] = author_escalation_receipt
    sessions.insert(0, waiting)
    save_sessions(sessions[:30])
    return session_id


def create_oop_intent_wait(*, repo_path: str, task_text: str,
                           stored_gap: dict, web_mode: str = "instant",
                           task_mode: str = "review", control: dict | None = None) -> str:
    """Persist one candidate-free OOP clarification in ordinary session history."""
    from core.oop_intent_session import validate_stored_gap

    resolved_repo = str(Path(repo_path).resolve())
    gap = validate_stored_gap(stored_gap, task_text=task_text, repo_path=resolved_repo)
    sessions = load_sessions()
    for existing in sessions:
        if (existing.get("clarification_kind") == "oop_intent"
                and existing.get("status") == "waiting_for_clarification"
                and (existing.get("oop_intent_gap") or {}).get("gap_id") == gap["gap_id"]
                and existing.get("query") == task_text
                and (control is None or existing.get("control") == control)
                and existing.get("repo_path") == resolved_repo):
            return existing["id"]
    session_id = "oop-intent-" + uuid.uuid4().hex
    waiting = {
        "id": session_id, "title": task_text[:40] or "OOP clarification",
        "query": task_text, "repo_path": resolved_repo,
        "mode": "oop_intent", "task_mode": task_mode,
        "web_mode": web_mode, "clarification_kind": "oop_intent",
        "status": "waiting_for_clarification", "oop_intent_gap": gap,
        "clarification_answer": None, "events": ["waiting_for_clarification"],
        "result": {"answer": gap["question"], "patch": "",
                   "status": "waiting_for_clarification", "patch_candidate": None,
                   "write_authority": False, "execution_authorized": False,
                   "auto_apply": False},
    }
    if task_mode == "patch" and control is not None:
        waiting["control"] = control
    sessions.insert(0, waiting)
    save_sessions(sessions[:30])
    return session_id


def update_oop_intent_wait(session_id: str, *, status: str,
                           answer: dict | None = None,
                           result: dict | None = None) -> bool:
    """Update only the matching OOP session; never touch RepairIntent state."""
    sessions = load_sessions()
    for session in sessions:
        if session.get("id") != session_id or session.get("clarification_kind") != "oop_intent":
            continue
        session["status"] = status
        if answer is not None:
            if session.get("clarification_answer") is None:
                session.setdefault("events", []).append("clarification_supplied")
            session["clarification_answer"] = answer
        if not session.get("events") or session["events"][-1] != status:
            session.setdefault("events", []).append(status)
        if result is not None:
            session["result"] = result
        save_sessions(sessions)
        return True
    return False


def update_repair_intent_wait(session_id: str, *, status: str,
                              answer: dict | None = None,
                              result: dict | None = None) -> bool:
    """Update only an existing repair-intent session, retaining its task and CONTROL."""
    sessions = load_sessions()
    for session in sessions:
        if session.get("id") != session_id or session.get("mode") != "repair_intent":
            continue
        session["status"] = status
        if answer is not None:
            if session.get("clarification_answer") is None:
                session.setdefault("events", []).append("clarification_supplied")
            session["clarification_answer"] = answer
            if isinstance(session.get("repair_intent_gap"), dict):
                session["repair_intent_gap"]["status"] = "clarification_supplied"
        if not session.get("events") or session["events"][-1] != status:
            session.setdefault("events", []).append(status)
        if result is not None:
            session["result"] = result
        save_sessions(sessions)
        return True
    return False


def list_sessions(
    include_archived: bool = False,
    include_deleted: bool = False,
) -> list[dict]:
    result = []
    for s in load_sessions():
        if s.get("deleted") and not include_deleted:
            continue
        if s.get("archived") and not include_archived:
            continue
        result.append(s)
    return result


def update_session_apply_outcome(
    session_id: str,
    *,
    repo_path: str | Path,
    patch_payload: dict[str, Any],
    response: dict[str, Any],
) -> bool:
    """Persist one terminal manual-Apply result on its existing session.

    The update is deliberately narrow: it rewrites only the already-persisted
    result payload and validation/diff surfaces.  Candidate/source contents are
    not copied into any new history structure; authorization receipts contain
    fingerprints only.
    """

    if not session_id:
        return False
    try:
        expected_repo = Path(repo_path).resolve()
    except (OSError, ValueError):
        return False
    sessions = load_sessions()
    for session in sessions:
        if session.get("id") != session_id:
            continue
        try:
            stored_repo = Path(str(session.get("repo_path") or "")).resolve()
        except (OSError, ValueError):
            return False
        if stored_repo != expected_repo:
            return False
        result = session.get("result")
        if not isinstance(result, dict):
            result = {}
            session["result"] = result
        result["patch"] = json.dumps(
            patch_payload, indent=2, ensure_ascii=False
        )
        result["validation"] = str(response.get("validation") or "")
        result["diff"] = str(response.get("diff") or "")
        result["manual_apply_outcome"] = {
            key: response.get(key)
            for key in (
                "success",
                "message",
                "human_approval_received",
                "execution_authorized",
                "execution_authority_source",
                "execution_attempted",
                "mutation_observed",
                "patch_applied",
                "application_status",
                "rollback_outcome_schema_version",
                "rollback_outcome",
                "rollback_status",
                "rollback_attempted",
                "rollback_completed",
                "rollback_verified",
                "rollback_performed",
                "remaining_changed_paths",
                "remaining_created_directories",
                "rollback_failure",
                "recovery_artifact_ids",
                "recovery_material_available",
                "recovery_material_error",
                "final_repository_changed",
                "final_state_verified",
                "final_validation_outcome",
                "human_apply_authorization_status",
                "human_apply_authorization_denial_reason",
                "human_apply_authorization_fingerprint",
            )
        }
        save_sessions(sessions)
        return True
    return False
