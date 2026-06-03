"""Lesson merge and archive operations.

All writes use helpers from core.lesson_store. No model calls anywhere.
"""
from __future__ import annotations

from core.lesson_store import (
    STATUS_ACTIVE,
    STATUS_CANDIDATE,
    _coerce_tags,
    get_lesson_by_id,
    patch_lesson_fields,
    save_raw_lesson_record,
    _generate_lesson_id,
    _lessons_root,
    _now_iso,
)


_MAX_SUMMARY_CHARS = 500


def _union_tags(lessons: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lesson in lessons:
        for tag in lesson.get("tags") or []:
            if isinstance(tag, str) and tag not in seen:
                seen.add(tag)
                out.append(tag)
    return out


def _join_summaries(lessons: list[dict]) -> str:
    parts = [l.get("summary", "").strip() for l in lessons if l.get("summary", "").strip()]
    joined = " | ".join(parts)
    if len(joined) > _MAX_SUMMARY_CHARS:
        return joined[:_MAX_SUMMARY_CHARS] + "…"
    return joined


def preview_merge(
    lessons: list[dict],
    *,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> tuple[dict, list[str]]:
    """Build a merged lesson preview dict without writing anything.

    Returns (preview_record, warnings).
    The preview_record has no id/created_at/updated_at.
    """
    if len(lessons) < 2:
        raise ValueError("preview_merge requires at least 2 lessons")

    warnings: list[str] = []

    active_ids = [l["id"] for l in lessons if l.get("status") == STATUS_ACTIVE]
    if active_ids:
        warnings.append(f"{len(active_ids)} active lesson(s) will be superseded")

    kinds = {l.get("kind") or "lesson" for l in lessons}
    if len(kinds) > 1:
        warnings.append(f"mixing lesson kinds: {sorted(kinds)}")
    resolved_kind = next(iter(kinds)) if len(kinds) == 1 else "mixed"

    merged_tags = _union_tags(lessons) if tags is None else _coerce_tags(tags)
    source_ids = [l["id"] for l in lessons]
    sources_data = [
        {
            "id": l["id"],
            "candidate": l.get("candidate") or {},
            "evaluation": l.get("evaluation") or {},
        }
        for l in lessons
    ]

    record = {
        "kind": resolved_kind,
        "status": STATUS_CANDIDATE,
        "active_knowledge_allowed": False,
        "scope": lessons[0].get("scope", "global"),
        "repo_scope_id": lessons[0].get("repo_scope_id"),
        "repo_path_hint": lessons[0].get("repo_path_hint"),
        "source": "merge",
        "source_report": None,
        "case_name": None,
        "title": title if title is not None else (lessons[0].get("title") or "Merged lesson"),
        "summary": summary if summary is not None else _join_summaries(lessons),
        "tags": merged_tags,
        "candidate": {},
        "evaluation": {
            "promotion": "needs_human_review",
            "active_knowledge_allowed": False,
            "score": 0.0,
            "reasons": ["merged lesson — human review required"],
        },
        "archived": False,
        "superseded_by": None,
        "supersedes": source_ids,
        "merge_sources": source_ids,
        "merge_sources_data": sources_data,
        "duplicate_of": None,
    }
    return record, warnings


def archive_lesson(
    lesson_id: str,
    *,
    repo_path: str | None = None,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    """Set archived=True on a candidate or blocked lesson.

    Idempotent. Raises ValueError if the lesson is active.
    """
    record = get_lesson_by_id(
        lesson_id, repo_path=repo_path, scope=scope, repo_scope_id=repo_scope_id
    )
    if record.get("status") == STATUS_ACTIVE:
        raise ValueError(f"cannot archive an active lesson: {lesson_id}")
    if record.get("archived"):
        return record
    return patch_lesson_fields(
        lesson_id,
        {"archived": True},
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
