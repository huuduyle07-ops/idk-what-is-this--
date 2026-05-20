"""Phase 6.0: persistent storage for lesson candidates.

Saves lesson records as JSON under `.agent/lessons/<bucket>/<id>.json` in the
AI project's own agent dir — never per-analyzed-repo — after running them
through `core.lesson_quality.evaluate_lesson_candidate`. Lessons are
org-wide knowledge; `repo_path` arguments are accepted for API stability
but ignored when resolving the storage root.

Storage is intentionally separate from retrieval. Phase 6.0 only persists records
and exposes promote/block controls; 6.2 will add the read-only retrieval helper
that walks `lessons/active/*.json`.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from config import get_agent_dir
from core.lesson_quality import (
    AUTO_APPROVED,
    BLOCKED,
    evaluate_lesson_candidate,
)


STATUS_CANDIDATE = "candidate"
STATUS_ACTIVE = "active"
STATUS_BLOCKED = "blocked"
LESSON_STATUSES = {STATUS_CANDIDATE, STATUS_ACTIVE, STATUS_BLOCKED}

_BUCKET_DIRS = {
    STATUS_CANDIDATE: "candidate",
    STATUS_ACTIVE: "active",
    STATUS_BLOCKED: "blocked",
}

_LESSON_ID_RE = re.compile(r"^\d{8}_\d{6}_\d{6}(-\d+)?$")

# Phase 6.2.2 — tag derivation
_TAG_TEXT_SPLIT_RE = re.compile(r"""[\s,;:.!?()\[\]{}<>"`'/\\]+""")
_TAG_STOPWORDS = frozenset({
    # English connectives
    "a", "an", "the", "and", "or", "but", "if",
    "of", "to", "in", "on", "at", "for", "with", "by", "from", "as",
    "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did",
    "i", "you", "we", "they", "it",
    "this", "that", "these", "those",
    # Generic action/problem words (mirror lesson_retrieval._QUERY_STOPWORDS)
    "fix", "bug", "patch", "issue", "problem",
    # Generic descriptive nouns commonly present in titles
    "case", "test", "lesson", "proposal",
})
_TAG_MIN_TOKEN_LEN = 4
_TAG_MAX_TEXT_TOKENS = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lessons_root(repo_path: str | None = None) -> Path:
    # Lessons are always stored in the AI project's own .agent/lessons/,
    # not under .agent/<target_tag>/, so indexing a target repo doesn't
    # pollute its workspace. `repo_path` is accepted for API compatibility
    # but intentionally ignored.
    root = get_agent_dir(None) / "lessons"
    for bucket in _BUCKET_DIRS.values():
        (root / bucket).mkdir(parents=True, exist_ok=True)
    return root


def _validate_lesson_id(lesson_id: str) -> None:
    if not isinstance(lesson_id, str) or not _LESSON_ID_RE.match(lesson_id):
        raise ValueError(f"invalid lesson id: {lesson_id!r}")


def _lesson_path(lessons_root: Path, status: str, lesson_id: str) -> Path:
    if status not in LESSON_STATUSES:
        raise ValueError(f"invalid lesson status: {status!r}")
    _validate_lesson_id(lesson_id)
    bucket = _BUCKET_DIRS[status]
    candidate = (lessons_root / bucket / f"{lesson_id}.json").resolve()
    try:
        candidate.relative_to(lessons_root.resolve())
    except ValueError as e:
        raise ValueError(f"lesson path escapes lessons root: {lesson_id!r}") from e
    return candidate


def _generate_lesson_id(lessons_root: Path) -> str:
    base = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    candidate_id = base
    suffix = 0
    while _find_lesson(lessons_root, candidate_id) is not None:
        suffix += 1
        candidate_id = f"{base}-{suffix}"
    return candidate_id


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically via temp file + os.replace.

    Mirrors core/dream_artifacts.py atomic_write_list_json.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _read_lesson(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _find_lesson(
    lessons_root: Path, lesson_id: str
) -> tuple[Path, str, dict] | None:
    """Search all three buckets for `lesson_id`.

    Returns `(path, bucket_status, record)` or None. If the same id appears in
    multiple buckets (e.g., a crash between atomic-write and unlink), prefers
    the entry whose `status` field matches its bucket name.
    """
    _validate_lesson_id(lesson_id)
    candidates: list[tuple[Path, str, dict]] = []
    for status, bucket in _BUCKET_DIRS.items():
        path = lessons_root / bucket / f"{lesson_id}.json"
        if not path.is_file():
            continue
        record = _read_lesson(path)
        if record is None:
            continue
        candidates.append((path, status, record))

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    for entry in candidates:
        _path, bucket_status, record = entry
        if record.get("status") == bucket_status:
            return entry
    return candidates[0]


def _status_routing(promotion: str | None, *, auto_active: bool) -> str:
    if promotion == BLOCKED:
        return STATUS_BLOCKED
    if promotion == AUTO_APPROVED and auto_active:
        return STATUS_ACTIVE
    return STATUS_CANDIDATE


def derive_lesson_tags(
    candidate: dict,
    *,
    case_name: str | None = None,
    title: str | None = None,
    summary: str | None = None,
) -> list[str]:
    """Deterministically derive a small list of tags from a lesson candidate.

    Tags surface in `lesson_retrieval.find_active_lessons` with a higher
    score than free-form title/summary matches, so they should be high-signal
    only: language, category, case_name slug, changed-file basenames, and a
    handful of distinctive content tokens from title/summary.

    Underscores in source strings are normalized to hyphens. Tokens are
    lowercased and deduped (insertion order preserved).
    """
    if not isinstance(candidate, dict):
        candidate = {}

    tags: list[str] = []

    language = _candidate_str(candidate, "language")
    if language:
        tags.append(language.lower())

    category = _candidate_str(candidate, "category")
    if category:
        tags.append(_normalize_tag(category))

    if isinstance(case_name, str) and case_name.strip():
        tags.append(_normalize_tag(case_name))

    changed_files = candidate.get("changed_files")
    if isinstance(changed_files, list):
        for entry in changed_files:
            if isinstance(entry, str) and entry.strip():
                stem = Path(entry).stem
                if stem:
                    tags.append(_normalize_tag(stem))

    text_pool_parts = [s for s in (title, summary) if isinstance(s, str) and s.strip()]
    if text_pool_parts:
        for token in _extract_content_tokens(" ".join(text_pool_parts)):
            tags.append(token)

    return _dedupe_tags(tags)


def _candidate_str(candidate: dict, key: str) -> str | None:
    value = candidate.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _normalize_tag(text: str) -> str:
    return text.strip().lower().replace("_", "-")


def _extract_content_tokens(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for piece in _TAG_TEXT_SPLIT_RE.split(text.lower()):
        token = piece.strip()
        if len(token) < _TAG_MIN_TOKEN_LEN:
            continue
        if token in _TAG_STOPWORDS:
            continue
        normalized = token.replace("_", "-")
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= _TAG_MAX_TEXT_TOKENS:
            break
    return out


def _dedupe_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        token = tag.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _coerce_tags(raw: Any) -> list[str]:
    """Normalize a caller-supplied tags argument to a clean list[str]."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, str):
            continue
        token = _normalize_tag(entry)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def save_candidate_lesson(
    candidate: dict,
    *,
    source: str = "manual",
    source_report: str | None = None,
    case_name: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
    repo_path: str | None = None,
) -> dict:
    """Evaluate `candidate` via lesson_quality and persist as a lesson record.

    If `tags` is None, tags are auto-derived via `derive_lesson_tags(...)`.
    Pass `tags=[]` to explicitly save with no tags.
    """
    evaluation = evaluate_lesson_candidate(candidate)
    promotion = evaluation.get("promotion")
    auto_active = bool(getattr(config, "LESSON_AUTO_ACTIVE", False))
    status = _status_routing(promotion, auto_active=auto_active)

    lessons_root = _lessons_root(repo_path)
    lesson_id = _generate_lesson_id(lessons_root)
    now = _now_iso()

    if tags is None:
        resolved_tags = derive_lesson_tags(
            candidate,
            case_name=case_name,
            title=title,
            summary=summary,
        )
    else:
        resolved_tags = _coerce_tags(tags)

    record = {
        "id": lesson_id,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "source": source,
        "source_report": source_report,
        "case_name": case_name,
        "title": title if title is not None else f"Lesson from {case_name or source}",
        "summary": summary if summary is not None else "",
        "tags": resolved_tags,
        "candidate": candidate,
        "evaluation": evaluation,
        # Top-level field strictly mirrors the bucket: only true when the file
        # lives in active/. Guard's original verdict is preserved in
        # `evaluation.active_knowledge_allowed`. Keeps the invariant
        # "top-level true => file in active/" so any code that reads this
        # field instead of checking the bucket can never pull a candidate.
        "active_knowledge_allowed": status == STATUS_ACTIVE,
    }

    path = _lesson_path(lessons_root, status, lesson_id)
    _atomic_write_json(path, record)
    return record


def list_lessons(
    status: str | None = None,
    repo_path: str | None = None,
) -> list[dict]:
    """Return lesson records, newest first by `created_at`.

    Filters by `status` if provided. Dedupes by `id` across buckets, preferring
    the entry whose `status` field matches its bucket name.
    """
    if status is not None and status not in LESSON_STATUSES:
        raise ValueError(f"invalid status: {status!r}")

    lessons_root = _lessons_root(repo_path)
    buckets = [status] if status else list(_BUCKET_DIRS.keys())

    by_id: dict[str, tuple[str, dict]] = {}
    for bucket_status in buckets:
        bucket_dir = lessons_root / _BUCKET_DIRS[bucket_status]
        if not bucket_dir.is_dir():
            continue
        for path in bucket_dir.glob("*.json"):
            record = _read_lesson(path)
            if record is None:
                continue
            lesson_id = record.get("id")
            if not isinstance(lesson_id, str):
                continue
            existing = by_id.get(lesson_id)
            if existing is None:
                by_id[lesson_id] = (bucket_status, record)
                continue
            existing_bucket, existing_record = existing
            if existing_record.get("status") == existing_bucket:
                continue
            if record.get("status") == bucket_status:
                by_id[lesson_id] = (bucket_status, record)

    records = [rec for _bucket, rec in by_id.values()]
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records


def find_lesson_by_source_report(
    source: str,
    source_report: str,
    repo_path: str | None = None,
) -> dict | None:
    """Return the newest lesson matching `source` and `source_report`.

    Searches candidate, active, and blocked buckets via `list_lessons`, so it
    can be used as an idempotency guard before creating source-derived lessons.
    """
    if not isinstance(source, str) or not source.strip():
        return None
    if not isinstance(source_report, str) or not source_report.strip():
        return None

    for lesson in list_lessons(repo_path=repo_path):
        if (
            lesson.get("source") == source
            and lesson.get("source_report") == source_report
        ):
            return lesson
    return None


def promote_lesson(lesson_id: str, repo_path: str | None = None) -> dict:
    """Move a candidate lesson to active.

    Idempotent: re-promoting an already-active lesson returns the existing
    record unchanged (no `updated_at` rewrite). Raises ValueError if the
    lesson is blocked, LookupError if the id is unknown, ValueError if the
    id format is invalid or escapes the lessons root.
    """
    _validate_lesson_id(lesson_id)
    lessons_root = _lessons_root(repo_path)

    found = _find_lesson(lessons_root, lesson_id)
    if found is None:
        raise LookupError(f"lesson not found: {lesson_id}")

    old_path, current_status, record = found

    if current_status == STATUS_BLOCKED:
        raise ValueError(f"cannot promote a blocked lesson: {lesson_id}")
    if current_status == STATUS_ACTIVE:
        return record

    record["status"] = STATUS_ACTIVE
    record["active_knowledge_allowed"] = True
    record["updated_at"] = _now_iso()

    new_path = _lesson_path(lessons_root, STATUS_ACTIVE, lesson_id)
    _atomic_write_json(new_path, record)
    if old_path != new_path:
        try:
            old_path.unlink(missing_ok=True)
        except OSError:
            pass
    return record


def block_lesson(lesson_id: str, repo_path: str | None = None) -> dict:
    """Move any lesson (candidate or active) to blocked.

    Idempotent: re-blocking an already-blocked lesson returns the existing
    record unchanged (no `updated_at` rewrite). Raises LookupError if the id
    is unknown, ValueError if the id format is invalid or escapes the lessons
    root.
    """
    _validate_lesson_id(lesson_id)
    lessons_root = _lessons_root(repo_path)

    found = _find_lesson(lessons_root, lesson_id)
    if found is None:
        raise LookupError(f"lesson not found: {lesson_id}")

    old_path, current_status, record = found

    if current_status == STATUS_BLOCKED:
        return record

    record["status"] = STATUS_BLOCKED
    record["active_knowledge_allowed"] = False
    record["updated_at"] = _now_iso()

    new_path = _lesson_path(lessons_root, STATUS_BLOCKED, lesson_id)
    _atomic_write_json(new_path, record)
    if old_path != new_path:
        try:
            old_path.unlink(missing_ok=True)
        except OSError:
            pass
    return record
