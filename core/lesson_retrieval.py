"""Phase 6.2: read-only retrieval over Active_Knowledge lessons.

Reads ONLY from `lessons/active/` via `core.lesson_store.list_lessons(status="active")`.
Never reads candidate or blocked buckets. Never writes, never calls a model,
never mutates a lesson record.

Phase 13.11a: the final ordering boundary (`find_active_lessons`) optionally
applies the Phase 13.9 Memory Temperature tie-breaker, gated by a
disabled-by-default config flag (`MEMORY_TEMPERATURE_RETRIEVAL_ENABLED`). When
the flag is false (the default) the ordering is an exact pass-through — no
reordering, no metadata, no mutation — so live behavior is unchanged. The
CONTROL prompt builder is untouched; it still consumes this boundary's output.
"""
from __future__ import annotations

import re
from typing import Any

from core.lesson_store import STATUS_ACTIVE, list_lessons
from core.memory_temperature_retrieval import (
    TIEBREAK_METADATA_KEY,
    apply_memory_temperature_tiebreaker,
)


_LIMIT_MIN = 1
_LIMIT_MAX = 20

_SCORE_CASE_NAME = 100
_SCORE_TAG = 25
_SCORE_LANGUAGE = 10
_SCORE_CATEGORY = 10
_SCORE_QUERY = 5

_PROMPT_MAX_REASONS = 3
_PROMPT_MAX_SUMMARY = 240

_KNOWN_LANGUAGE_PREFIXES = {
    "python", "py", "go", "rust", "cpp", "c", "ts", "js",
    "html", "java", "csharp", "cs", "kotlin", "swift",
}

# Stopwords dropped from query tokenization. Two groups:
#   (1) English connectives ("the", "of", ...) so queries like "Fix the X bug"
#       don't match every lesson on "the".
#   (2) Generic problem/action nouns ("fix", "bug", "patch", "issue",
#       "problem") that appear in nearly every lesson title/summary. Without
#       this, a query like "Fix the JS null bug" would match an unrelated
#       C++ lesson just because both summaries contain "fix" or "bug".
# Domain identifiers (case_name slugs, language names, identifiers like
# `compound`, `inventory`, `null`, `patch_plan`) stay through tokenization.
_QUERY_STOPWORDS = frozenset({
    # English connectives
    "a", "an", "the",
    "and", "or", "but", "if",
    "of", "to", "in", "on", "at", "for", "with", "by", "from", "as",
    "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did",
    "i", "you", "we", "they", "it",
    "this", "that", "these", "those",
    # Generic problem/action words — present in almost every lesson
    "fix", "bug", "patch", "issue", "problem",
})

# Whitespace + sentence punctuation. Hyphens and underscores are preserved
# so identifiers like "auto-approval" and "off_by_one" stay as one token.
_QUERY_SPLIT_RE = re.compile(r'[\s,;.!?()\[\]{}<>"`\']+')


def _tokenize_query(query: str | None) -> list[str]:
    """Split a free-form query into lowercase content tokens.

    Drops short tokens (<2 chars) and a small English stopword list.
    Returns [] for empty / whitespace-only / all-stopword queries; the
    caller should treat that as "no query filter" rather than "no match".
    """
    if not query:
        return []
    pieces = _QUERY_SPLIT_RE.split(query.lower())
    out: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        token = piece.strip()
        if len(token) < 2:
            continue
        if token in _QUERY_STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def list_active_lessons(repo_path: str | None = None) -> list[dict]:
    """Return active, retrieval-eligible lessons.

    Lessons live in a single global bucket (`.agent/lessons/active/`) in the
    AI project's own agent dir; `repo_path` is accepted for API stability
    but does not change the read scope.

    Defensive double-check: filters anything where `status != "active"` or
    top-level `active_knowledge_allowed` is not True. The storage layer
    enforces the invariant, but a corrupted file or future bug must not
    leak a candidate or tampered record into context.
    """
    out: list[dict] = []
    seen_ids: set[str] = set()
    for record in list_lessons(status=STATUS_ACTIVE, repo_path=repo_path):
        if not isinstance(record, dict):
            continue
        if record.get("status") != STATUS_ACTIVE:
            continue
        if record.get("active_knowledge_allowed") is not True:
            continue
        lesson_id = record.get("id")
        if not isinstance(lesson_id, str) or lesson_id in seen_ids:
            continue
        seen_ids.add(lesson_id)
        out.append(record)
    return out


def find_active_lessons(
    *,
    repo_path: str | None = None,
    case_name: str | None = None,
    language: str | None = None,
    category: str | None = None,
    query: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Find active lessons ranked by deterministic keyword scoring.

    Reads ONLY from `list_active_lessons`. No writes, no LLM calls.

    Ranking signals (priority order):
      - exact `case_name` match  → +100
      - `language` match         → +10
      - `category` match         → +10
      - `query` substring match  → +5 (binary; one boost regardless of hits)

    Tie-break: `updated_at` desc, then `created_at` desc.

    When any filter is set, lessons that score 0 are dropped. When no filter
    is set, the top `limit` lessons by recency are returned.

    `limit` is coerced to int and clamped to [1, 20]. Returned records are
    shallow-copied and carry an extra `_match_score` integer.
    """
    limit_clamped = _clamp_limit(limit)

    lessons = list_active_lessons(repo_path=repo_path)

    case_name_norm = (case_name or "").strip()
    language_norm = (language or "").strip().lower()
    category_norm = (category or "").strip().lower()
    # Tokenize once; a query of only stopwords yields [] and is treated as
    # "no query filter" rather than dropping every lesson.
    query_tokens = _tokenize_query(query)
    has_filter = bool(case_name_norm or language_norm or category_norm or query_tokens)

    scored: list[tuple[int, dict]] = []
    for lesson in lessons:
        score = _score_lesson(
            lesson,
            case_name=case_name_norm,
            language=language_norm,
            category=category_norm,
            query_tokens=query_tokens,
        )
        if has_filter and score <= 0:
            continue
        scored.append((score, lesson))

    # Three-pass stable sort: least significant key first, most significant last.
    # Final order: score desc, updated_at desc, created_at desc.
    scored.sort(key=lambda p: _iso_or_empty(p[1].get("created_at")), reverse=True)
    scored.sort(key=lambda p: _iso_or_empty(p[1].get("updated_at")), reverse=True)
    scored.sort(key=lambda p: p[0], reverse=True)

    out: list[dict] = []
    for score, lesson in scored[:limit_clamped]:
        decorated = dict(lesson)
        decorated["_match_score"] = score
        out.append(decorated)
    return _maybe_apply_temperature_tiebreaker(out)


def _temperature_tiebreaker_flags() -> tuple[bool, bool]:
    """Read the Phase 13.11a tie-breaker flags from config (fail-closed).

    Returns ``(enabled, tiebreak_only)``. Defaults — and the fallback on any
    import/attribute error — are ``(False, True)`` so the live ordering is
    exactly unchanged. The flags are read here (at the call site), never inside
    the pure tie-breaker helper.
    """
    try:
        import config as _config
    except Exception:
        return False, True
    enabled = bool(getattr(_config, "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED", False))
    tiebreak_only = bool(getattr(_config, "MEMORY_TEMPERATURE_TIEBREAK_ONLY", True))
    return enabled, tiebreak_only


def _maybe_apply_temperature_tiebreaker(lessons: list[dict]) -> list[dict]:
    """Optionally reorder near-equal lessons by Memory Temperature (Phase 13.11a).

    Default-off (flag false): returns ``lessons`` unchanged — same objects, same
    order, no metadata, no mutation — so the CONTROL prompt is unaffected.

    Enabled: maps each lesson's integer ``_match_score`` onto the ``score`` key
    the tie-breaker groups by, runs the conservative tie-break, then re-projects
    the resulting order back onto the original lesson records (preserving every
    field and the original ``_match_score``) with only the debug tie-break
    metadata attached. Inputs are never mutated. Cold lessons are never
    hard-filtered and frozen/audit-only/blocked lessons are only sunk last,
    never surfaced or removed — that behavior lives in the 13.9 helper.
    """
    enabled, tiebreak_only = _temperature_tiebreaker_flags()
    if not enabled:
        return lessons

    view = [
        dict(lesson, score=_coerce_match_score(lesson.get("_match_score")))
        for lesson in lessons
    ]
    adjusted = apply_memory_temperature_tiebreaker(
        view, enabled=True, tiebreak_only=tiebreak_only, now=None
    )

    out: list[dict] = []
    for item in adjusted:
        meta = item.get(TIEBREAK_METADATA_KEY) if isinstance(item, dict) else None
        original_index: int | None = None
        if isinstance(meta, dict):
            rank = meta.get("original_rank")
            if isinstance(rank, int) and 1 <= rank <= len(lessons):
                original_index = rank - 1
        if original_index is not None:
            # Original record (with its real `_match_score`) + debug metadata;
            # drop the throwaway `score` view key by not copying it.
            record = dict(lessons[original_index])
            record[TIEBREAK_METADATA_KEY] = meta
        else:
            # Defensive fallback: keep the adjusted copy but strip the view key.
            record = dict(item)
            record.pop("score", None)
        out.append(record)
    return out


def _coerce_match_score(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def format_lessons_for_prompt(lessons: list[dict], max_chars: int = 4000) -> str:
    """Render a compact text block of lessons for future prompt use.

    Includes title, case_name, source, summary, and up to a few key reasons.
    Never includes the raw `candidate` payload. Output is capped at
    `max_chars`; if exceeded, the trailing text is replaced with an ellipsis.
    Returns an empty string for an empty/None input.
    """
    if not lessons:
        return ""
    if not isinstance(max_chars, int) or max_chars <= 0:
        max_chars = 4000

    blocks: list[str] = []
    for i, lesson in enumerate(lessons, start=1):
        if not isinstance(lesson, dict):
            continue
        block = _format_one_lesson(lesson, index=i)
        if block:
            blocks.append(block)

    text = "\n\n---\n\n".join(blocks)
    if len(text) > max_chars:
        cutoff = max(1, max_chars - 1)
        text = text[:cutoff].rstrip() + "…"
    return text


# --- internals ------------------------------------------------------------


def _clamp_limit(value: Any) -> int:
    if isinstance(value, bool):
        coerced = int(value)
    elif isinstance(value, int):
        coerced = value
    else:
        try:
            coerced = int(value)
        except (TypeError, ValueError):
            coerced = 5
    if coerced < _LIMIT_MIN:
        return _LIMIT_MIN
    if coerced > _LIMIT_MAX:
        return _LIMIT_MAX
    return coerced


def _score_lesson(
    lesson: dict,
    *,
    case_name: str,
    language: str,
    category: str,
    query_tokens: list[str],
) -> int:
    score = 0

    lesson_case = _coerce_str(lesson.get("case_name")) or ""
    lesson_case = lesson_case.strip()
    if case_name and lesson_case and case_name == lesson_case:
        score += _SCORE_CASE_NAME

    candidate = lesson.get("candidate")
    candidate = candidate if isinstance(candidate, dict) else {}

    if language:
        lang_val = (
            _coerce_str(lesson.get("language"))
            or _coerce_str(candidate.get("language"))
            or _language_from_case_name(lesson_case)
            or ""
        )
        if lang_val.lower() == language:
            score += _SCORE_LANGUAGE

    if category:
        cat_val = (
            _coerce_str(lesson.get("category"))
            or _coerce_str(candidate.get("category"))
            or ""
        )
        if cat_val.lower() == category:
            score += _SCORE_CATEGORY

    if query_tokens:
        haystack = _build_haystack(lesson, candidate)
        # Binary: any token hit grants the query boost. Keeps scoring
        # deterministic and prevents long queries from dominating ranking.
        if any(token in haystack for token in query_tokens):
            score += _SCORE_QUERY

        # Phase 6.2.2: tag match grants a higher boost than a generic
        # title/summary substring hit. Lessons without `tags` (older
        # records) silently skip this — they can still match via query.
        tag_haystack = _build_tag_haystack(lesson)
        if tag_haystack and any(token in tag_haystack for token in query_tokens):
            score += _SCORE_TAG

    return score


def _build_tag_haystack(lesson: dict) -> str:
    tags = lesson.get("tags")
    if not isinstance(tags, list):
        return ""
    parts = [t.lower() for t in tags if isinstance(t, str) and t.strip()]
    return " ".join(parts)


def _language_from_case_name(case_name: str) -> str | None:
    if not case_name:
        return None
    head = case_name.split("_", 1)[0].lower()
    if head in _KNOWN_LANGUAGE_PREFIXES:
        return head
    return None


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _build_haystack(lesson: dict, candidate: dict) -> str:
    parts: list[str] = []
    for key in ("title", "summary", "case_name", "source", "source_report"):
        v = lesson.get(key)
        if isinstance(v, str):
            parts.append(v)

    for value in candidate.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)

    evaluation = lesson.get("evaluation")
    if isinstance(evaluation, dict):
        reasons = evaluation.get("reasons")
        if isinstance(reasons, list):
            for r in reasons:
                if isinstance(r, str):
                    parts.append(r)

    return " ".join(parts).lower()


def _iso_or_empty(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _format_one_lesson(lesson: dict, *, index: int) -> str:
    title = _coerce_str(lesson.get("title")) or "Untitled lesson"
    title = title.strip() or "Untitled lesson"
    case = (_coerce_str(lesson.get("case_name")) or "").strip()
    source = (_coerce_str(lesson.get("source")) or "").strip()
    summary = (_coerce_str(lesson.get("summary")) or "").strip()
    if len(summary) > _PROMPT_MAX_SUMMARY:
        summary = summary[: _PROMPT_MAX_SUMMARY - 1].rstrip() + "…"

    reasons: list[str] = []
    evaluation = lesson.get("evaluation")
    if isinstance(evaluation, dict):
        raw_reasons = evaluation.get("reasons")
        if isinstance(raw_reasons, list):
            for r in raw_reasons:
                if isinstance(r, str) and r.strip():
                    reasons.append(r.strip())
                if len(reasons) >= _PROMPT_MAX_REASONS:
                    break

    lines = [f"## Lesson {index}: {title}"]
    if case:
        lines.append(f"case: {case}")
    if source:
        lines.append(f"source: {source}")
    if summary:
        lines.append(f"summary: {summary}")
    if reasons:
        lines.append("reasons:")
        for r in reasons:
            lines.append(f"  - {r}")
    return "\n".join(lines)
