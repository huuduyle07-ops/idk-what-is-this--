"""Lesson merge and archive operations.

All writes use helpers from core.lesson_store. No model calls anywhere.
"""
from __future__ import annotations

from core.lesson_store import (
    KIND_ANTI_LESSON,
    KIND_LESSON,
    STATUS_ACTIVE,
    STATUS_CANDIDATE,
    _coerce_tags,
    get_lesson_by_id,
    normalize_lesson_kind,
    patch_lesson_fields,
    # Used by create_merge (Task 4):
    save_raw_lesson_record,  # noqa: F401
    _generate_lesson_id,  # noqa: F401
    _lessons_root,  # noqa: F401
    _now_iso,  # noqa: F401
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
    parts = [lesson.get("summary", "").strip() for lesson in lessons if lesson.get("summary", "").strip()]
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

    active_ids = [lesson["id"] for lesson in lessons if lesson.get("status") == STATUS_ACTIVE]
    if active_ids:
        warnings.append(f"{len(active_ids)} active lesson(s) will be superseded")

    kinds = {lesson.get("kind") or "lesson" for lesson in lessons}
    if len(kinds) > 1:
        warnings.append(f"mixing lesson kinds: {sorted(kinds)}")
    resolved_kind = next(iter(kinds)) if len(kinds) == 1 else "mixed"

    merged_tags = _union_tags(lessons) if tags is None else _coerce_tags(tags)
    source_ids = [lesson["id"] for lesson in lessons]
    sources_data = [
        {
            "id": lesson["id"],
            "candidate": lesson.get("candidate") or {},
            "evaluation": lesson.get("evaluation") or {},
        }
        for lesson in lessons
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


def create_merge(
    source_ids: list[str],
    title: str,
    summary: str,
    tags: list[str],
    *,
    repo_path: str | None = None,
    scope: str | None = None,
    repo_scope_id: str | None = None,
    confirm_supersede_active: bool = False,
    confirm_mix_kinds: bool = False,
) -> tuple[dict, list[str]]:
    """Create a merged lesson candidate from source_ids.

    Returns (new_record, superseded_ids).
    Raises ValueError if guards not confirmed; LookupError if any ID not found.
    The merged record is always candidate and never auto-promoted.

    Phase 11.1: merging a normal lesson with an anti-lesson is a HARD block and
    raises ValueError regardless of `confirm_mix_kinds` (now vestigial — kept
    only so existing callers/routes that pass it keep working). An anti+anti
    merge is allowed and produces a candidate anti-lesson with
    `active_knowledge_allowed=False`.

    Note: writes the merged record before patching sources. If a source patch
    fails mid-loop, earlier sources will be marked superseded_by but later ones
    will not. No rollback is performed — this is a known limitation of the
    single-file-at-a-time store design.
    """
    if len(source_ids) < 2:
        raise ValueError("create_merge requires at least 2 source IDs")

    lessons = [
        get_lesson_by_id(
            lid, repo_path=repo_path, scope=scope, repo_scope_id=repo_scope_id
        )
        for lid in source_ids
    ]

    active_ids = [lesson["id"] for lesson in lessons if lesson.get("status") == STATUS_ACTIVE]
    if active_ids and not confirm_supersede_active:
        raise ValueError(
            f"active lessons require confirm_supersede_active=True: {active_ids}"
        )

    # Phase 11.1: a normal lesson and an anti-lesson are semantic opposites
    # ("do X" vs "do NOT do X") and must never be merged. This is a HARD block:
    # `confirm_mix_kinds` cannot override it (the flag is retained only for API
    # compatibility — since `lesson` and `anti_lesson` are the only kinds, the
    # only possible mix is normal+anti, so it is now vestigial). An anti+anti
    # merge is allowed and yields a candidate anti-lesson (see preview_merge).
    kinds = {normalize_lesson_kind(lesson.get("kind")) for lesson in lessons}
    if KIND_LESSON in kinds and KIND_ANTI_LESSON in kinds:
        raise ValueError(
            "cannot merge a normal lesson with an anti-lesson "
            "(anti-lessons may only be merged with other anti-lessons)"
        )

    record, _ = preview_merge(lessons, title=title, summary=summary, tags=tags)

    # Assign identity
    lessons_root = _lessons_root(repo_path)
    lesson_id = _generate_lesson_id(lessons_root)
    now = _now_iso()
    record["id"] = lesson_id
    record["created_at"] = now
    record["updated_at"] = now

    # Write merged record first — patch sources only after successful write
    save_raw_lesson_record(record, repo_path=repo_path)

    superseded: list[str] = []
    for lid in source_ids:
        patch_lesson_fields(
            lid,
            {"superseded_by": lesson_id},
            repo_path=repo_path,
            scope=scope,
            repo_scope_id=repo_scope_id,
        )
        superseded.append(lid)

    return record, superseded
