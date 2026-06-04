"""Phase 11.2 — manual anti-lesson creation.

Operator-driven creation of *candidate* anti-lessons. This module only validates
input and delegates persistence to
``core.lesson_store.save_candidate_lesson(kind="anti_lesson")`` — it never writes
files directly, never promotes, never calls a model, and never touches the
network / subprocess / Docker.

Anti-lessons stay inert (Phase 11.1): candidate status,
``active_knowledge_allowed=False``, and excluded from live retrieval. There is no
auto-creation path here; a human supplies every field.
"""
from __future__ import annotations

import re
from typing import Any

from core import lesson_store


_MAX_SUMMARY_CHARS = 500
_MAX_EVIDENCE_REFS = 50
_MAX_REF_CHARS = 500
_MAX_RELATED_IDS = 50

# Reuse the store's lesson-id shape for related_lesson_ids validation.
_LESSON_ID_RE = re.compile(r"^\d{8}_\d{6}_\d{6}(-\d+)?$")
# Windows drive prefix, e.g. "C:\..." or "c:/...".
_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _require_text(value: Any, field: str) -> str:
    """Return a non-empty stripped string or raise ValueError.

    Rejects empty / whitespace-only / non-string input so empty or meaningless
    anti-lessons cannot be created.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _reject_unsafe_ref(ref: str) -> None:
    """Reject an evidence ref that could escape a notional artifacts root.

    Evidence refs are untrusted operator input. We never open them in this
    phase, but we still refuse anything that looks like a traversal/absolute
    path so a later consumer cannot be tricked into reading outside an
    artifacts directory: NUL bytes, absolute paths, Windows drive paths, or any
    ``..`` path segment (either separator).
    """
    if "\x00" in ref:
        raise ValueError(f"invalid evidence ref: {ref!r}")
    normalized = ref.replace("\\", "/")
    if normalized.startswith("/"):
        raise ValueError(f"evidence ref must be relative: {ref!r}")
    if _DRIVE_RE.match(ref):
        raise ValueError(f"evidence ref must be relative: {ref!r}")
    if any(seg == ".." for seg in normalized.split("/")):
        raise ValueError(f"evidence ref escapes root: {ref!r}")


def _coerce_str_items(raw: Any, field: str) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        items: list[Any] = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        raise ValueError(f"{field} must be a list of strings")
    out: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{field} must be strings")
        token = item.strip()
        if token:
            out.append(token)
    return out


def _clean_evidence_refs(raw: Any) -> list[str]:
    refs = _coerce_str_items(raw, "evidence_refs")
    out: list[str] = []
    for ref in refs:
        if len(ref) > _MAX_REF_CHARS:
            raise ValueError("evidence ref is too long")
        _reject_unsafe_ref(ref)
        out.append(ref)
    if len(out) > _MAX_EVIDENCE_REFS:
        raise ValueError("too many evidence_refs")
    return out


def _clean_related_ids(raw: Any) -> list[str]:
    ids = _coerce_str_items(raw, "related_lesson_ids")
    out: list[str] = []
    seen: set[str] = set()
    for rid in ids:
        if not _LESSON_ID_RE.match(rid):
            raise ValueError(f"invalid related lesson id: {rid!r}")
        if rid in seen:
            continue
        seen.add(rid)
        out.append(rid)
    if len(out) > _MAX_RELATED_IDS:
        raise ValueError("too many related_lesson_ids")
    return out


def _default_summary(tempting: str, why: str, safer: str) -> str:
    text = f"Do NOT: {tempting} Why: {why} Instead: {safer}"
    if len(text) > _MAX_SUMMARY_CHARS:
        return text[: _MAX_SUMMARY_CHARS - 1].rstrip() + "…"
    return text


def create_manual_anti_lesson(
    *,
    title: Any,
    tempting_wrong_pattern: Any,
    why_wrong: Any,
    safer_alternative: Any,
    summary: Any = None,
    evidence_refs: Any = None,
    related_lesson_ids: Any = None,
    tags: list[str] | None = None,
    source: str = "manual",
    source_report: str | None = None,
    repo_path: str | None = None,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    """Validate operator input and persist a *candidate* anti-lesson.

    Required (each non-empty after strip): ``title``, ``tempting_wrong_pattern``,
    ``why_wrong``, ``safer_alternative``. ``evidence_refs`` are guarded against
    path traversal; ``related_lesson_ids`` must be valid lesson-id strings.

    Persistence always goes through
    ``lesson_store.save_candidate_lesson(kind="anti_lesson")``, so the result is
    a candidate with ``active_knowledge_allowed=False`` — never active, never
    auto-promoted, and not retrieval-eligible (Phase 11.1 guarantees). Raises
    ValueError on invalid input.
    """
    title_v = _require_text(title, "title")
    tempting_v = _require_text(tempting_wrong_pattern, "tempting_wrong_pattern")
    why_v = _require_text(why_wrong, "why_wrong")
    safer_v = _require_text(safer_alternative, "safer_alternative")

    refs = _clean_evidence_refs(evidence_refs)
    related = _clean_related_ids(related_lesson_ids)

    if isinstance(summary, str) and summary.strip():
        summary_v = summary.strip()
    else:
        summary_v = _default_summary(tempting_v, why_v, safer_v)

    source_v = source.strip() if isinstance(source, str) and source.strip() else "manual"
    report_v = (
        source_report.strip()
        if isinstance(source_report, str) and source_report.strip()
        else None
    )

    candidate = {
        "anti_lesson": True,
        "tempting_wrong_pattern": tempting_v,
        "why_wrong": why_v,
        "safer_alternative": safer_v,
        "evidence_refs": refs,
        "related_lesson_ids": related,
    }

    return lesson_store.save_candidate_lesson(
        candidate,
        source=source_v,
        source_report=report_v,
        title=title_v,
        summary=summary_v,
        tags=tags,
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
        kind=lesson_store.KIND_ANTI_LESSON,
    )
