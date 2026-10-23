"""Admission of current-review and future-design OOP gaps to session history."""
from __future__ import annotations

from typing import Any
from hashlib import sha256
from pathlib import Path

from core.input_understanding import understand_request
from core.oop_intent_session import make_stored_future_design_gap, make_stored_gap
from core.oop_semantic_review import review_acquired_java_evidence
from core.proposed_design_intent import project_proposed_design_intent
from core.repository_identity import derive_repository_id
from web.session_store import create_oop_intent_wait


def _wait_result(stored: dict, session_id: str, detection: dict | None = None) -> dict:
    result = {
        "answer": stored["question"], "context": "", "graph": "",
        "state": "", "patch": "", "validation": "",
        "patch_candidate": None, "patch_plan": None,
        "write_authority": False, "execution_authorized": False,
        "auto_apply": False, "repair_scope_authority": False,
        "status": "waiting_for_clarification",
        "clarification_kind": "oop_intent",
        "clarification_session_id": session_id,
        "patch_author_calls": 0,
    }
    if detection is not None:
        result["oop_intent_detection"] = detection
    return result


def _fail_closed_result(detection: Any) -> dict:
    return {
        "answer": "Future-design evidence is not complete enough for clarification or authoring.",
        "context": "", "graph": "", "state": "", "patch": "", "validation": "",
        "patch_candidate": None, "patch_plan": None,
        "write_authority": False, "execution_authorized": False,
        "auto_apply": False, "repair_scope_authority": False,
        "status": detection.status, "code": detection.status,
        "patch_author_calls": 0, "oop_intent_detection": detection.as_dict(),
    }


def _future_design_applies(contract: Any, design: Any) -> bool:
    evidence = getattr(contract, "design_evidence", None)
    return bool(
        getattr(design, "relationships", ())
        or getattr(design, "state_commitments", ())
        or getattr(design, "behavior_gates", ())
        or getattr(design, "conflicts", ())
        or getattr(evidence, "relationships", ())
        or getattr(evidence, "state_commitments", ())
        or getattr(evidence, "behavior_gates", ())
        or getattr(evidence, "inheritance_prohibitions", ())
        or getattr(evidence, "overflow", ())
    )


def _context_from_raw(*, raw: bytes, path: str, design: Any,
                      repository_id: str, target_symbol: str = "") -> Any:
    """Project one already selected exact Java buffer; never discover a file."""
    from core.class_semantic_context import project_class_semantic_context
    from core.treesitter_parse import structural_definitions

    if not isinstance(raw, bytes) or not path.lower().endswith(".java"):
        return None
    try:
        definitions = [
            item for item in structural_definitions(raw.decode("utf-8"), "java")["definitions"]
            if item["kind"] in {"class", "interface", "enum", "record"}
        ]
    except (UnicodeError, KeyError, TypeError, ValueError, RecursionError):
        return None
    if target_symbol:
        target_name = target_symbol.rsplit("::", 1)[-1]
        matches = [item for item in definitions if item.get("name") == target_name]
        if len(matches) != 1:
            return None
        target = matches[0]
    else:
        preferred = [
            *(item.parent for item in getattr(design, "relationships", ())),
            *(item.child for item in getattr(design, "relationships", ())),
            *(item.owner for item in getattr(design, "state_commitments", ())),
        ]
        matches = [item for name in dict.fromkeys(preferred) for item in definitions
                   if item.get("name") == name]
        if len(matches) > 1:
            return None
        target = matches[0] if matches else None
        if target is None:
            if preferred or len(definitions) != 1:
                return None
            target = definitions[0]
    if target is None:
        return None
    return project_class_semantic_context(
        raw=raw, language="java", file=path, target=target,
        expected_source_fingerprint=sha256(raw).hexdigest(),
        repository_id=repository_id)


def _detect_future(*, contract: Any, design: Any, context: Any,
                   raw: bytes, repository_id: str) -> Any:
    from core.oop_intent_detector import detect_missing_future_design_contract

    return detect_missing_future_design_contract(
        task_contract=contract, design_intent=design,
        current_context=context, current_source=raw,
        repository_id=repository_id)


def _admit_detection(*, detection: Any, repo_path: str, task_text: str,
                     task_mode: str, web_mode: str = "instant",
                     control: dict | None = None) -> dict | None:
    stored = make_stored_future_design_gap(
        detection, task_text=task_text, repo_path=repo_path)
    if stored is None:
        return None
    session_id = create_oop_intent_wait(
        repo_path=repo_path, task_text=task_text, stored_gap=stored,
        task_mode=task_mode, web_mode=web_mode, control=control)
    return _wait_result(stored, session_id, detection.as_dict())


def _future_from_analysis_evidence(
    *, evidence: Any, repo_path: str, task_text: str,
    task_mode: str, web_mode: str,
) -> tuple[dict | None, bool]:
    contract = understand_request(task_text)
    design = project_proposed_design_intent(contract)
    applies = _future_design_applies(contract, design)
    if not applies:
        return None, False
    repository_id = derive_repository_id(repo_path)
    selected: tuple[Any, bytes] | None = None
    for item in getattr(evidence, "items", ()):
        path = getattr(item, "path", "")
        if (not isinstance(path, str) or not path.lower().endswith(".java")
                or getattr(item, "truncated", True)
                or (getattr(item, "repository_id", "") not in ("", repository_id))):
            continue
        try:
            root = Path(repo_path).resolve()
            target = (root / path).resolve()
            target.relative_to(root)
            raw = target.read_bytes()
        except (OSError, ValueError, TypeError):
            continue
        context = _context_from_raw(
            raw=raw, path=path, design=design, repository_id=repository_id)
        if context is not None:
            selected = (context, raw)
            break
    context, raw = selected if selected is not None else (None, b"")
    detection = _detect_future(
        contract=contract, design=design, context=context, raw=raw,
        repository_id=repository_id)
    if detection.status == "clarification_required":
        return _admit_detection(
            detection=detection, repo_path=repo_path, task_text=task_text,
            task_mode=task_mode, web_mode=web_mode), True
    if detection.status == "no_gap":
        return None, False
    return _fail_closed_result(detection), True


def admit_future_design_control_wait(
    *, control: dict, repo_path: str, task_text: str, web_mode: str = "instant",
) -> tuple[dict | None, bool]:
    """Run DETECT.2 before RepairScope construction and patch authoring.

    The named CONTROL target is already acquired evidence.  This function may
    freshness-read that exact path; it never inventories, searches, or expands
    the edit set.
    """
    contract = understand_request(task_text)
    design = project_proposed_design_intent(contract)
    applies = _future_design_applies(contract, design)
    if not applies:
        return None, False
    repository_id = derive_repository_id(repo_path)
    intent = control.get("patch_intent") or {}
    relative = next((intent.get(key) for key in ("relative_path", "file", "target_file")
                     if isinstance(intent.get(key), str) and intent.get(key)), "")
    context, raw = None, b""
    if isinstance(relative, str) and relative.lower().endswith(".java"):
        try:
            root = Path(repo_path).resolve()
            target = (root / relative).resolve()
            target.relative_to(root)
            raw = target.read_bytes()
            context = _context_from_raw(
                raw=raw, path=relative, design=design,
                repository_id=repository_id,
                target_symbol=str(intent.get("target_symbol")
                                  or intent.get("target_symbol_full") or ""))
        except (OSError, ValueError, TypeError):
            context, raw = None, b""
    detection = _detect_future(
        contract=contract, design=design, context=context, raw=raw,
        repository_id=repository_id)
    if detection.status == "clarification_required":
        return _admit_detection(
            detection=detection, repo_path=repo_path, task_text=task_text,
            task_mode="patch", web_mode=web_mode, control=control), True
    if detection.status == "no_gap":
        return None, False
    return _fail_closed_result(detection), True


def admit_oop_review_wait(*, evidence: Any, repo_path: str, task_text: str,
                          task_mode: str = "review", web_mode: str = "instant") -> dict | None:
    """Reuse already acquired analysis evidence; informational 1C stays normal."""
    future, future_owned = _future_from_analysis_evidence(
        evidence=evidence, repo_path=repo_path, task_text=task_text,
        task_mode=task_mode, web_mode=web_mode)
    if future is not None or future_owned:
        return future
    contract = understand_request(task_text)
    reviews = review_acquired_java_evidence(
        evidence=evidence, repository_root=repo_path,
        task_contract=contract)
    for review in reviews:
        stored = make_stored_gap(review, task_text=task_text, repo_path=repo_path)
        if stored is None:
            continue
        session_id = create_oop_intent_wait(
            repo_path=repo_path, task_text=task_text, stored_gap=stored,
            task_mode=task_mode, web_mode=web_mode)
        return _wait_result(stored, session_id)
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
