"""Admission of an existing CTX.OOP.1C review to session history."""
from __future__ import annotations

from typing import Any
from hashlib import sha256
from pathlib import Path

from core.input_understanding import understand_request
from core.oop_intent_session import make_stored_gap
from core.oop_semantic_review import review_acquired_java_evidence
from web.session_store import create_oop_intent_wait


def admit_oop_review_wait(*, evidence: Any, repo_path: str, task_text: str,
                          task_mode: str = "review", web_mode: str = "instant") -> dict | None:
    """Reuse already acquired analysis evidence; informational 1C stays normal."""
    reviews = review_acquired_java_evidence(
        evidence=evidence, repository_root=repo_path,
        task_contract=understand_request(task_text))
    for review in reviews:
        stored = make_stored_gap(review, task_text=task_text, repo_path=repo_path)
        if stored is None:
            continue
        session_id = create_oop_intent_wait(
            repo_path=repo_path, task_text=task_text, stored_gap=stored,
            task_mode=task_mode, web_mode=web_mode)
        return {
            "answer": stored["question"], "context": "", "graph": "",
            "state": "", "patch": "", "validation": "",
            "patch_candidate": None, "patch_plan": None,
            "write_authority": False, "execution_authorized": False,
            "auto_apply": False, "status": "waiting_for_clarification",
            "clarification_kind": "oop_intent",
            "clarification_session_id": session_id,
        }
    return None


def admit_oop_patch_wait(*, control: dict, repo_path: str,
                         task_text: str) -> dict | None:
    """Review the existing exact patch target before ambiguous authoring.

    No search or new candidate is performed. A missing/unsupported target
    leaves the established patch pipeline's own gates in charge.
    """
    from core.class_semantic_context import project_class_semantic_context
    from core.oop_semantic_review import review_oop_semantics
    from core.treesitter_parse import structural_definitions

    scope = control.get("repair_scope") or {}
    target_info = scope.get("primary_target") or {}
    relative = target_info.get("file")
    if not isinstance(relative, str) or not relative.lower().endswith(".java"):
        return None
    try:
        root = Path(repo_path).resolve()
        target_path = (root / relative).resolve()
        target_path.relative_to(root)
        raw = target_path.read_bytes()
        source = raw.decode("utf-8")
        classes = [item for item in structural_definitions(source, "java")["definitions"]
                   if item["kind"] in {"class", "interface", "enum", "record"}]
        if len(classes) != 1:
            return None
        context = project_class_semantic_context(
            raw=raw, language="java", file=relative, target=classes[0],
            expected_source_fingerprint=sha256(raw).hexdigest())
        review = review_oop_semantics(
            context=context, current_source=raw,
            task_contract=understand_request(task_text))
        stored = make_stored_gap(review, task_text=task_text, repo_path=repo_path)
        if stored is None:
            return None
        session_id = create_oop_intent_wait(
            repo_path=repo_path, task_text=task_text, stored_gap=stored,
            task_mode="patch", control=control)
        return {
            "answer": stored["question"], "patch": "",
            "patch_candidate": None, "patch_plan": None,
            "write_authority": False, "execution_authorized": False,
            "auto_apply": False, "status": "waiting_for_clarification",
            "clarification_kind": "oop_intent",
            "clarification_session_id": session_id,
        }
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RecursionError):
        return None
