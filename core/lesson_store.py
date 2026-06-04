"""Persistent storage for lesson candidates and active lessons.

Legacy/global lessons stay under `.agent/lessons/{candidate,active,blocked}/`.
Repo-scoped lessons live under
`.agent/lessons/repos/<repo_scope_id>/{candidate,active,blocked}/`.

The storage root is still the AI project's own `.agent/lessons/` directory.
`repo_path` only selects a safe scope bucket inside that root.
"""
from __future__ import annotations

import hashlib
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

SCOPE_GLOBAL = "global"
SCOPE_REPO = "repo"
LESSON_SCOPES = {SCOPE_GLOBAL, SCOPE_REPO}

# Phase 11.1 — lesson kind. A normal lesson says "do this pattern when this
# evidence appears"; an anti-lesson says "do NOT do this tempting but wrong
# pattern". Anti-lessons are stored as first-class records but stay inert:
# never auto-activated and never retrieval-eligible (see core.lesson_retrieval).
KIND_LESSON = "lesson"
KIND_ANTI_LESSON = "anti_lesson"
LESSON_KINDS = {KIND_LESSON, KIND_ANTI_LESSON}

_BUCKET_DIRS = {
    STATUS_CANDIDATE: "candidate",
    STATUS_ACTIVE: "active",
    STATUS_BLOCKED: "blocked",
}

_LESSON_ID_RE = re.compile(r"^\d{8}_\d{6}_\d{6}(-\d+)?$")
_REPO_SCOPE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")

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


def validate_lesson_kind(kind: Any) -> str:
    """Return `kind` unchanged if it is a recognized lesson kind, else raise.

    Unlike `normalize_lesson_kind`, this supplies NO default — a missing or
    unknown value (including None) raises ValueError. Use it to reject bad
    kinds on write paths.
    """
    if kind not in LESSON_KINDS:
        raise ValueError(f"invalid lesson kind: {kind!r}")
    return kind


def normalize_lesson_kind(kind: Any) -> str:
    """Coerce a lesson `kind` to a canonical value.

    Missing / None / blank string → "lesson" (legacy records predate `kind` and
    are normal lessons). A recognized kind is returned unchanged. Any other
    value raises ValueError via `validate_lesson_kind`.
    """
    if kind is None:
        return KIND_LESSON
    if isinstance(kind, str) and not kind.strip():
        return KIND_LESSON
    return validate_lesson_kind(kind)


def is_anti_lesson(record: Any) -> bool:
    """True iff `record` is a dict whose kind is the anti-lesson kind.

    Lenient and side-effect-free: never raises. A missing or unrecognized kind
    is treated as a normal lesson (returns False), so this is safe to call on
    arbitrary/legacy records in read and retrieval paths.
    """
    if not isinstance(record, dict):
        return False
    return record.get("kind") == KIND_ANTI_LESSON


def _lessons_root(repo_path: str | None = None) -> Path:
    # Lessons are always stored in the AI project's own .agent/lessons/.
    # `repo_path` selects a scope bucket under this root; it never changes
    # the root to the analyzed repo's workspace.
    root = get_agent_dir(None) / "lessons"
    _ensure_bucket_dirs(root)
    (root / "repos").mkdir(parents=True, exist_ok=True)
    return root


def _ensure_bucket_dirs(root: Path) -> None:
    for bucket in _BUCKET_DIRS.values():
        (root / bucket).mkdir(parents=True, exist_ok=True)


def _validate_scope(scope: str | None) -> None:
    if scope is not None and scope not in LESSON_SCOPES:
        raise ValueError(f"invalid lesson scope: {scope!r}")


def _validate_repo_scope_id(repo_scope_id: str) -> None:
    if (
        not isinstance(repo_scope_id, str)
        or not _REPO_SCOPE_ID_RE.match(repo_scope_id)
        or repo_scope_id in {".", ".."}
    ):
        raise ValueError(f"invalid repo_scope_id: {repo_scope_id!r}")


def _safe_repo_path_hint(repo_path: str | None) -> str | None:
    if not repo_path:
        return None
    try:
        name = Path(repo_path).expanduser().resolve().name
    except OSError:
        name = Path(repo_path).name
    safe = re.sub(r"[^A-Za-z0-9._ -]", "", name).strip()
    return safe[:80] or None


def repo_scope_id_for_path(repo_path: str | Path | None) -> str:
    """Return a stable, filesystem-safe scope id for `repo_path`."""
    if repo_path is None or not str(repo_path).strip():
        raise ValueError("repo_path is required for repo-scoped lessons")

    try:
        resolved = Path(repo_path).expanduser().resolve()
    except OSError:
        resolved = Path(repo_path).expanduser().absolute()

    tag = ""
    try:
        if resolved.is_dir():
            from core.project_tag import build_project_tag

            tag = build_project_tag(str(resolved))
    except Exception:
        tag = ""

    if tag and tag != "unknown-project":
        candidate = tag.strip().lower()
        if _REPO_SCOPE_ID_RE.match(candidate):
            return candidate

    digest = hashlib.sha256(str(resolved).encode("utf-8", errors="replace")).hexdigest()
    return f"repo-{digest[:16]}"


def _resolve_repo_scope(
    repo_path: str | Path | None,
    repo_scope_id: str | None = None,
) -> tuple[str, str | None]:
    expected = repo_scope_id_for_path(repo_path)
    if repo_scope_id:
        _validate_repo_scope_id(repo_scope_id)
        if repo_scope_id != expected:
            raise ValueError("repo_scope_id does not match repo_path")
    return expected, _safe_repo_path_hint(str(repo_path) if repo_path is not None else None)


def _resolve_save_scope(
    candidate: dict,
    *,
    source: str,
    repo_path: str | None,
    scope: str | None,
    repo_scope_id: str | None = None,
) -> tuple[str, str | None, str | None]:
    _validate_scope(scope)
    if scope is None:
        candidate_source = candidate.get("source") if isinstance(candidate, dict) else None
        if source == "benchmark_report" or candidate_source == "benchmark_report":
            scope = SCOPE_GLOBAL
        elif repo_path:
            scope = SCOPE_REPO
        else:
            scope = SCOPE_GLOBAL

    if scope == SCOPE_GLOBAL:
        if repo_scope_id:
            _validate_repo_scope_id(repo_scope_id)
            raise ValueError("repo_scope_id is only valid for repo-scoped lessons")
        return SCOPE_GLOBAL, None, None

    resolved_id, hint = _resolve_repo_scope(repo_path, repo_scope_id)
    return SCOPE_REPO, resolved_id, hint


def _scope_root(lessons_root: Path, scope: str, repo_scope_id: str | None = None) -> Path:
    _validate_scope(scope)
    if scope == SCOPE_GLOBAL:
        root = lessons_root
    else:
        if not repo_scope_id:
            raise ValueError("repo_scope_id is required for repo-scoped lessons")
        _validate_repo_scope_id(repo_scope_id)
        root = lessons_root / "repos" / repo_scope_id
    _ensure_bucket_dirs(root)
    return root


def _validate_lesson_id(lesson_id: str) -> None:
    if not isinstance(lesson_id, str) or not _LESSON_ID_RE.match(lesson_id):
        raise ValueError(f"invalid lesson id: {lesson_id!r}")


def _lesson_path(scope_root: Path, status: str, lesson_id: str) -> Path:
    if status not in LESSON_STATUSES:
        raise ValueError(f"invalid lesson status: {status!r}")
    _validate_lesson_id(lesson_id)
    bucket = _BUCKET_DIRS[status]
    candidate = (scope_root / bucket / f"{lesson_id}.json").resolve()
    try:
        candidate.relative_to(scope_root.resolve())
    except ValueError as e:
        raise ValueError(f"lesson path escapes lessons root: {lesson_id!r}") from e
    return candidate


def _generate_lesson_id(lessons_root: Path) -> str:
    base = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    candidate_id = base
    suffix = 0
    while _find_lesson_anywhere(lessons_root, candidate_id) is not None:
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


def _find_lesson_in_scope(
    scope_root: Path, lesson_id: str
) -> tuple[Path, str, dict] | None:
    """Search all three buckets for `lesson_id`.

    Returns `(path, bucket_status, record)` or None. If the same id appears in
    multiple buckets (e.g., a crash between atomic-write and unlink), prefers
    the entry whose `status` field matches its bucket name.
    """
    _validate_lesson_id(lesson_id)
    candidates: list[tuple[Path, str, dict]] = []
    for status in _BUCKET_DIRS:
        path = _lesson_path(scope_root, status, lesson_id)
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


def _iter_existing_scope_roots(
    lessons_root: Path,
) -> list[tuple[str, str | None, Path, str | None]]:
    roots: list[tuple[str, str | None, Path, str | None]] = [
        (SCOPE_GLOBAL, None, _scope_root(lessons_root, SCOPE_GLOBAL), None)
    ]
    repos_root = lessons_root / "repos"
    if repos_root.is_dir():
        for path in sorted(repos_root.iterdir(), key=lambda p: p.name):
            if not path.is_dir():
                continue
            try:
                _validate_repo_scope_id(path.name)
            except ValueError:
                continue
            roots.append((SCOPE_REPO, path.name, _scope_root(lessons_root, SCOPE_REPO, path.name), None))
    return roots


def _find_lesson_anywhere(
    lessons_root: Path, lesson_id: str
) -> tuple[Path, str, dict] | None:
    for _scope, _repo_scope_id, scope_root, _hint in _iter_existing_scope_roots(lessons_root):
        found = _find_lesson_in_scope(scope_root, lesson_id)
        if found is not None:
            return found
    return None


def _normalize_record(
    record: dict,
    *,
    bucket_status: str,
    scope: str,
    repo_scope_id: str | None,
    repo_path_hint: str | None,
) -> dict:
    normalized = dict(record)
    normalized["status"] = bucket_status
    normalized["scope"] = scope
    normalized["repo_scope_id"] = repo_scope_id if scope == SCOPE_REPO else None
    normalized["repo_path_hint"] = repo_path_hint if scope == SCOPE_REPO else None
    # Phase 11.1: keep `kind` canonical on read. Tolerate legacy (missing) and
    # corrupt values by defaulting to "lesson" rather than raising in a read
    # path — only write paths reject unknown kinds.
    raw_kind = record.get("kind")
    normalized["kind"] = raw_kind if raw_kind in LESSON_KINDS else KIND_LESSON
    if bucket_status == STATUS_ACTIVE:
        normalized["active_knowledge_allowed"] = (
            normalized.get("active_knowledge_allowed") is True
        )
    else:
        normalized["active_knowledge_allowed"] = False
    return normalized


def _scope_roots_for_query(
    lessons_root: Path,
    *,
    repo_path: str | None = None,
    include_global: bool = True,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> list[tuple[str, str | None, Path, str | None]]:
    _validate_scope(scope)
    if scope == SCOPE_GLOBAL:
        if repo_scope_id:
            _validate_repo_scope_id(repo_scope_id)
            raise ValueError("repo_scope_id is only valid for repo-scoped lessons")
        return [(SCOPE_GLOBAL, None, _scope_root(lessons_root, SCOPE_GLOBAL), None)]

    if scope == SCOPE_REPO:
        resolved_id, hint = _resolve_repo_scope(repo_path, repo_scope_id)
        return [
            (
                SCOPE_REPO,
                resolved_id,
                _scope_root(lessons_root, SCOPE_REPO, resolved_id),
                hint,
            )
        ]

    if repo_scope_id:
        _validate_repo_scope_id(repo_scope_id)
        if not repo_path:
            raise ValueError("repo_path is required when repo_scope_id is provided")

    if repo_path:
        resolved_id, hint = _resolve_repo_scope(repo_path, repo_scope_id)
        roots = [
            (
                SCOPE_REPO,
                resolved_id,
                _scope_root(lessons_root, SCOPE_REPO, resolved_id),
                hint,
            )
        ]
        if include_global:
            roots.append((SCOPE_GLOBAL, None, _scope_root(lessons_root, SCOPE_GLOBAL), None))
        return roots

    return [(SCOPE_GLOBAL, None, _scope_root(lessons_root, SCOPE_GLOBAL), None)]


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
    scope: str | None = None,
    repo_scope_id: str | None = None,
    kind: str = KIND_LESSON,
) -> dict:
    """Evaluate `candidate` via lesson_quality and persist as a lesson record.

    If `tags` is None, tags are auto-derived via `derive_lesson_tags(...)`.
    Pass `tags=[]` to explicitly save with no tags.

    `kind` defaults to "lesson". Pass `kind="anti_lesson"` to store an
    anti-lesson; unknown kinds are rejected. Anti-lessons are inert (Phase
    11.1): they never auto-activate even when the quality guard auto-approved
    and `LESSON_AUTO_ACTIVE` is on, and `active_knowledge_allowed` is forced
    false. A blocked verdict still routes an anti-lesson to the blocked bucket.
    """
    resolved_kind = normalize_lesson_kind(kind)
    evaluation = evaluate_lesson_candidate(candidate)
    promotion = evaluation.get("promotion")
    auto_active = bool(getattr(config, "LESSON_AUTO_ACTIVE", False))
    if resolved_kind == KIND_ANTI_LESSON:
        # Anti-lessons never auto-activate. A blocked verdict still routes to
        # blocked (anti-lessons may be blocked); everything else stays a
        # candidate awaiting an explicit, future-gated activation path.
        status = STATUS_BLOCKED if promotion == BLOCKED else STATUS_CANDIDATE
    else:
        status = _status_routing(promotion, auto_active=auto_active)
    scope_name, resolved_repo_scope_id, repo_path_hint = _resolve_save_scope(
        candidate,
        source=source,
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )

    lessons_root = _lessons_root(repo_path)
    scope_root = _scope_root(lessons_root, scope_name, resolved_repo_scope_id)
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
        "scope": scope_name,
        "repo_scope_id": resolved_repo_scope_id,
        "repo_path_hint": repo_path_hint,
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
        # Phase b2 additions
        "kind": resolved_kind,
        "archived": False,
        "superseded_by": None,
        "supersedes": [],
        "merge_sources": [],
        "merge_sources_data": [],
        "duplicate_of": None,
    }

    path = _lesson_path(scope_root, status, lesson_id)
    _atomic_write_json(path, record)
    return record


def list_lessons(
    status: str | None = None,
    repo_path: str | None = None,
    include_global: bool = True,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> list[dict]:
    """Return lesson records, newest first by `created_at`.

    Filters by `status` if provided. Dedupes by `id` across buckets, preferring
    the entry whose `status` field matches its bucket name.

    Scope (via `_scope_roots_for_query`): an explicit `scope` of "global" or
    "repo" reads only that bucket; otherwise the read scope depends on
    `repo_path` — when given (and `include_global=True`, the default) it reads
    the **union** of the repo-scoped bucket and the global bucket, and when
    omitted it reads the global bucket only.
    """
    if status is not None and status not in LESSON_STATUSES:
        raise ValueError(f"invalid status: {status!r}")

    lessons_root = _lessons_root(repo_path)
    buckets = [status] if status else list(_BUCKET_DIRS.keys())
    scope_roots = _scope_roots_for_query(
        lessons_root,
        repo_path=repo_path,
        include_global=include_global,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )

    by_key: dict[tuple[str, str | None, str], tuple[str, dict]] = {}
    for scope_name, resolved_repo_scope_id, scope_root, repo_path_hint in scope_roots:
        for bucket_status in buckets:
            bucket_dir = scope_root / _BUCKET_DIRS[bucket_status]
            if not bucket_dir.is_dir():
                continue
            for path in bucket_dir.glob("*.json"):
                record = _read_lesson(path)
                if record is None:
                    continue
                lesson_id = record.get("id")
                if not isinstance(lesson_id, str):
                    continue
                normalized = _normalize_record(
                    record,
                    bucket_status=bucket_status,
                    scope=scope_name,
                    repo_scope_id=resolved_repo_scope_id,
                    repo_path_hint=repo_path_hint,
                )
                key = (scope_name, resolved_repo_scope_id, lesson_id)
                existing = by_key.get(key)
                if existing is None:
                    by_key[key] = (bucket_status, normalized)
                    continue
                existing_bucket, existing_record = existing
                if existing_record.get("status") == existing_bucket:
                    continue
                if record.get("status") == bucket_status:
                    by_key[key] = (bucket_status, normalized)

    records = [rec for _bucket, rec in by_key.values()]
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


def _find_lesson_for_operation(
    lessons_root: Path,
    lesson_id: str,
    *,
    repo_path: str | None = None,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> tuple[Path, str, str, str | None, str | None, dict] | None:
    scope_roots = _scope_roots_for_query(
        lessons_root,
        repo_path=repo_path,
        include_global=True,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    for scope_name, resolved_repo_scope_id, scope_root, repo_path_hint in scope_roots:
        found = _find_lesson_in_scope(scope_root, lesson_id)
        if found is None:
            continue
        old_path, current_status, record = found
        normalized = _normalize_record(
            record,
            bucket_status=current_status,
            scope=scope_name,
            repo_scope_id=resolved_repo_scope_id,
            repo_path_hint=repo_path_hint,
        )
        return (
            old_path,
            current_status,
            scope_name,
            resolved_repo_scope_id,
            repo_path_hint,
            normalized,
        )
    return None


def promote_lesson(
    lesson_id: str,
    repo_path: str | None = None,
    *,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    """Move a candidate lesson to active.

    Idempotent: re-promoting an already-active lesson returns the existing
    record unchanged (no `updated_at` rewrite). Raises ValueError if the
    lesson is blocked, LookupError if the id is unknown, ValueError if the
    id format is invalid or escapes the lessons root.
    """
    _validate_lesson_id(lesson_id)
    lessons_root = _lessons_root(repo_path)

    found = _find_lesson_for_operation(
        lessons_root,
        lesson_id,
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    if found is None:
        raise LookupError(f"lesson not found: {lesson_id}")

    old_path, current_status, scope_name, resolved_repo_scope_id, repo_path_hint, record = found

    if current_status == STATUS_BLOCKED:
        raise ValueError(f"cannot promote a blocked lesson: {lesson_id}")
    if current_status == STATUS_ACTIVE:
        return record

    record["status"] = STATUS_ACTIVE
    record["scope"] = scope_name
    record["repo_scope_id"] = resolved_repo_scope_id
    record["repo_path_hint"] = repo_path_hint
    record["active_knowledge_allowed"] = True
    record["updated_at"] = _now_iso()

    target_root = _scope_root(lessons_root, scope_name, resolved_repo_scope_id)
    new_path = _lesson_path(target_root, STATUS_ACTIVE, lesson_id)
    _atomic_write_json(new_path, record)
    if old_path != new_path:
        try:
            old_path.unlink(missing_ok=True)
        except OSError:
            pass
    return record


def block_lesson(
    lesson_id: str,
    repo_path: str | None = None,
    *,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    """Move any lesson (candidate or active) to blocked.

    Idempotent: re-blocking an already-blocked lesson returns the existing
    record unchanged (no `updated_at` rewrite). Raises LookupError if the id
    is unknown, ValueError if the id format is invalid or escapes the lessons
    root.
    """
    _validate_lesson_id(lesson_id)
    lessons_root = _lessons_root(repo_path)

    found = _find_lesson_for_operation(
        lessons_root,
        lesson_id,
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    if found is None:
        raise LookupError(f"lesson not found: {lesson_id}")

    old_path, current_status, scope_name, resolved_repo_scope_id, repo_path_hint, record = found

    if current_status == STATUS_BLOCKED:
        return record

    record["status"] = STATUS_BLOCKED
    record["scope"] = scope_name
    record["repo_scope_id"] = resolved_repo_scope_id
    record["repo_path_hint"] = repo_path_hint
    record["active_knowledge_allowed"] = False
    record["updated_at"] = _now_iso()

    target_root = _scope_root(lessons_root, scope_name, resolved_repo_scope_id)
    new_path = _lesson_path(target_root, STATUS_BLOCKED, lesson_id)
    _atomic_write_json(new_path, record)
    if old_path != new_path:
        try:
            old_path.unlink(missing_ok=True)
        except OSError:
            pass
    return record


def get_lesson_by_id(
    lesson_id: str,
    repo_path: str | None = None,
    *,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    """Return a normalized lesson record by ID. Raises LookupError if not found."""
    _validate_lesson_id(lesson_id)
    lessons_root = _lessons_root(repo_path)
    found = _find_lesson_for_operation(
        lessons_root,
        lesson_id,
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    if found is None:
        raise LookupError(f"lesson not found: {lesson_id}")
    _, _, _, _, _, record = found
    return record


def patch_lesson_fields(
    lesson_id: str,
    fields: dict,
    repo_path: str | None = None,
    *,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    """Update fields on an existing lesson record in-place (atomic).

    The file stays in its current bucket. Cannot change 'id' or 'status'.
    """
    _forbidden = {"id", "status", "active_knowledge_allowed"}
    bad = _forbidden & set(fields)
    if bad:
        raise ValueError(f"patch_lesson_fields: cannot change {bad!r}")

    _validate_lesson_id(lesson_id)
    lessons_root = _lessons_root(repo_path)
    found = _find_lesson_for_operation(
        lessons_root,
        lesson_id,
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    if found is None:
        raise LookupError(f"lesson not found: {lesson_id}")

    path, current_status, scope_name, resolved_repo_scope_id, repo_path_hint, record = found
    record.update(fields)
    record["updated_at"] = _now_iso()
    _atomic_write_json(path, record)
    return _normalize_record(
        record,
        bucket_status=current_status,
        scope=scope_name,
        repo_scope_id=resolved_repo_scope_id,
        repo_path_hint=repo_path_hint,
    )


def save_raw_lesson_record(
    record: dict,
    *,
    repo_path: str | None = None,
) -> dict:
    """Write a pre-built lesson record directly to the candidate bucket (atomic).

    The record must already have a valid 'id' and status='candidate'.
    Used by lesson_merge.create_merge() to write merged records.
    """
    lesson_id = record.get("id")
    _validate_lesson_id(lesson_id)
    if record.get("status") != STATUS_CANDIDATE:
        raise ValueError("save_raw_lesson_record: status must be 'candidate'")
    # Copy before mutating so the caller's dict is untouched; canonicalize the
    # kind (missing → "lesson", unknown → ValueError) so raw writes can't smuggle
    # in an invalid kind.
    record = dict(record)
    record["kind"] = normalize_lesson_kind(record.get("kind"))
    scope_name = record.get("scope", SCOPE_GLOBAL)
    _validate_scope(scope_name)
    resolved_repo_scope_id = record.get("repo_scope_id")
    lessons_root = _lessons_root(repo_path)
    scope_root = _scope_root(lessons_root, scope_name, resolved_repo_scope_id)
    path = _lesson_path(scope_root, STATUS_CANDIDATE, lesson_id)
    _atomic_write_json(path, record)
    return record
