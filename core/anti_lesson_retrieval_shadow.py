"""Phase 11.6 — Anti-Lesson Retrieval Shadow Mode.

A *read-only* shadow retrieval layer. For a given query (and optional context),
it reports which anti-lessons *would* be relevant if anti-lessons were enabled
later — and changes nothing about live behavior:

  * ``build_anti_lesson_shadow_retrieval`` / ``format_..._markdown`` are pure
    (they take an already-loaded list and never touch the store);
  * ``load_anti_lesson_shadow_retrieval`` is the only store-aware entry — it
    *reads* lessons via ``lesson_store.list_lessons`` and never mutates anything;
  * nothing here injects into CONTROL, modifies active retrieval, runs Dream / the
    mutation oracle / benchmarks / patching / a model, and nothing
    creates/promotes/blocks/merges a lesson.

Matching is deterministic and cheap: normalized token overlap across a few
fields. No embeddings, no model calls. Every match is flagged ``shadow_only`` and
the result carries a ``blocked_actions`` list making the contract explicit.

This is the read-only precursor to a *future*, default-off CONTROL integration.
"""
from __future__ import annotations

import re
from typing import Any

from core import lesson_store
from core.lesson_store import _now_iso, is_anti_lesson


SHADOW_RETRIEVAL_TITLE = "Anti-Lesson Shadow Retrieval"
SHADOW_GUARDRAIL = (
    "Shadow retrieval is report-only. These anti-lessons are not injected into "
    "active retrieval or CONTROL prompts."
)

BLOCKED_ACTIONS = (
    "inject_into_control",
    "modify_active_retrieval",
    "patch",
    "benchmark",
    "dream",
    "model_call",
    "promote",
)

_DEFAULT_MAX_ITEMS = 5
_MAX_ITEMS_CAP = 50

# Per-field weights (binary: a field that contains any query token grants its
# weight once). Mirrors the existing active-retrieval style of cheap token hits.
_WEIGHT_TITLE = 5
_WEIGHT_SUMMARY = 3
_WEIGHT_TEMPTING = 4
_WEIGHT_WHY = 3
_WEIGHT_SAFER = 2
_WEIGHT_CONTEXT_EVIDENCE = 3
_WEIGHT_CONTEXT_RELATED = 3

# Whitespace + punctuation splitter; hyphens and underscores are preserved so
# identifiers like "off_by_one" / "auto-approval" stay one token.
_SPLIT_RE = re.compile(r"[^0-9a-z_\-]+")
_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "is", "are",
    "be", "it", "this", "that", "with", "as", "by", "at", "from", "into",
    "make", "made", "do", "not",
}


# ── small pure helpers ───────────────────────────────────────────────────────


def _candidate(record: dict) -> dict:
    cand = record.get("candidate") if isinstance(record, dict) else None
    return cand if isinstance(cand, dict) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def _scope_of(record: dict) -> str:
    return "repo" if record.get("scope") == "repo" else "global"


def _tokenize(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for piece in _SPLIT_RE.split(text.lower()):
        token = piece.strip("-_")
        if len(token) < 2 or token in _STOPWORDS or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _haystack(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().split())


def _field_matches(value: Any, query_tokens: list[str]) -> bool:
    if not query_tokens:
        return False
    haystack = _haystack(value)
    if not haystack:
        return False
    return any(token in haystack for token in query_tokens)


def _ref_norm(value: Any) -> str:
    return value.replace("\\", "/").strip().lower() if isinstance(value, str) else ""


def _ref_set(values: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(values, list):
        for v in values:
            norm = _ref_norm(v)
            if norm:
                out.add(norm)
    return out


def _clamp_max_items(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_ITEMS
    return max(1, min(n, _MAX_ITEMS_CAP))


# ── scoring ──────────────────────────────────────────────────────────────────


def _score_anti(record: dict, query_tokens: list[str], context: dict | None) -> tuple[int, list[str]]:
    cand = _candidate(record)
    score = 0
    reasons: list[str] = []

    if _field_matches(record.get("title"), query_tokens):
        score += _WEIGHT_TITLE
        reasons.append("title match")
    if _field_matches(record.get("summary"), query_tokens):
        score += _WEIGHT_SUMMARY
        reasons.append("summary match")
    if _field_matches(cand.get("tempting_wrong_pattern"), query_tokens):
        score += _WEIGHT_TEMPTING
        reasons.append("tempting_wrong_pattern match")
    if _field_matches(cand.get("why_wrong"), query_tokens):
        score += _WEIGHT_WHY
        reasons.append("why_wrong match")
    if _field_matches(cand.get("safer_alternative"), query_tokens):
        score += _WEIGHT_SAFER
        reasons.append("safer_alternative match")

    if context:
        ctx_evidence = _ref_set(context.get("evidence_refs"))
        ctx_source = _ref_norm(context.get("source_report"))
        rec_evidence = _ref_set(cand.get("evidence_refs"))
        rec_source = _ref_norm(record.get("source_report"))
        evidence_overlap = bool(ctx_evidence & rec_evidence)
        source_overlap = bool(ctx_source and rec_source and ctx_source == rec_source)
        if evidence_overlap or source_overlap:
            score += _WEIGHT_CONTEXT_EVIDENCE
            reasons.append("evidence/source_report overlap")

        ctx_related = _ref_set(context.get("related_lesson_ids"))
        rec_related = _ref_set(cand.get("related_lesson_ids"))
        if ctx_related & rec_related:
            score += _WEIGHT_CONTEXT_RELATED
            reasons.append("related_lesson_ids match")

    return score, reasons


def _match_row(record: dict, score: int, reasons: list[str]) -> dict:
    cand = _candidate(record)
    return {
        "lesson_id": record.get("id"),
        "title": _text(record.get("title")),
        "status": record.get("status") or "candidate",
        "scope": _scope_of(record),
        "score": score,
        "reasons": reasons,
        "tempting_wrong_pattern": _text(cand.get("tempting_wrong_pattern")),
        "why_wrong": _text(cand.get("why_wrong")),
        "safer_alternative": _text(cand.get("safer_alternative")),
        "duplicate_of": record.get("duplicate_of"),
        "related_lesson_ids": _str_list(cand.get("related_lesson_ids")),
        "evidence_refs": _str_list(cand.get("evidence_refs")),
        # Always true: this layer never feeds the live agent path.
        "shadow_only": True,
    }


def build_anti_lesson_shadow_retrieval(
    query: str,
    records: list[dict],
    *,
    context: dict | None = None,
    max_items: int = _DEFAULT_MAX_ITEMS,
    generated_at: str | None = None,
) -> dict:
    """Rank anti-lessons against ``query`` from an already-loaded ``records`` list.

    Only anti-lessons are considered; normal lessons are never returned. Pure —
    never reads the store, never mutates input, never calls a model, never
    executes anything. See module docstring for the safety contract.
    """
    q = query if isinstance(query, str) else ""
    query_tokens = _tokenize(q)
    ctx = context if isinstance(context, dict) else None

    records = [r for r in (records or []) if isinstance(r, dict)]
    anti = [r for r in records if is_anti_lesson(r)]

    scored: list[tuple[int, str, dict, list[str]]] = []
    skipped: list[dict] = []
    for record in anti:
        score, reasons = _score_anti(record, query_tokens, ctx)
        if score <= 0:
            skipped.append({
                "lesson_id": record.get("id"),
                "title": _text(record.get("title")),
                "reason": "no query match",
            })
            continue
        scored.append((score, str(record.get("id") or ""), record, reasons))

    # Deterministic: score desc, then lesson_id asc.
    scored.sort(key=lambda t: (-t[0], t[1]))

    max_n = _clamp_max_items(max_items)
    selected = [_match_row(record, score, reasons) for score, _id, record, reasons in scored[:max_n]]
    for score, _id, record, _reasons in scored[max_n:]:
        # Explicit, not silent: matches beyond the cap are recorded under skipped.
        skipped.append({
            "lesson_id": record.get("id"),
            "title": _text(record.get("title")),
            "reason": f"exceeds max_items cap ({max_n})",
        })

    return {
        "title": SHADOW_RETRIEVAL_TITLE,
        "generated_at": generated_at,
        "query": q,
        "guardrail": SHADOW_GUARDRAIL,
        "total_anti_lessons_considered": len(anti),
        "max_items": max_n,
        "selected_matches": selected,
        "skipped": skipped,
        "blocked_actions": list(BLOCKED_ACTIONS),
    }


def load_anti_lesson_shadow_retrieval(
    query: str,
    *,
    repo_path: str | None = None,
    scope: str | None = None,
    repo_scope_id: str | None = None,
    include_global: bool = True,
    max_items: int = _DEFAULT_MAX_ITEMS,
    context: dict | None = None,
    generated_at: str | None = None,
) -> dict:
    """Read lessons from the store and build a shadow retrieval result.

    The only store-aware entry point. It performs a single READ
    (``lesson_store.list_lessons``), keeps only ``kind="anti_lesson"`` records
    (candidate/active alike — all reported as ``shadow_only``), and delegates to
    the pure builder. It never writes.
    """
    lessons = lesson_store.list_lessons(
        repo_path=repo_path,
        include_global=include_global,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    anti = [r for r in lessons if is_anti_lesson(r)]
    return build_anti_lesson_shadow_retrieval(
        query,
        anti,
        context=context,
        max_items=max_items,
        generated_at=generated_at if generated_at is not None else _now_iso(),
    )


# ── Markdown ─────────────────────────────────────────────────────────────────


def _md_escape_cell(value: Any) -> str:
    text = value if isinstance(value, str) else ("" if value is None else str(value))
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _md_inline(value: Any) -> str:
    text = value if isinstance(value, str) else ("" if value is None else str(value))
    return " ".join(text.split())


def _truncate(text: str, limit: int = 80) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def format_anti_lesson_shadow_retrieval_markdown(result: dict) -> str:
    """Render a shadow retrieval ``result`` dict as Markdown (pure)."""
    if not isinstance(result, dict):
        result = {}
    matches = result.get("selected_matches") or []
    skipped = result.get("skipped") or []

    lines: list[str] = []
    lines.append(f"# {result.get('title') or SHADOW_RETRIEVAL_TITLE}")
    lines.append("")
    lines.append(f"_generated_at: {result.get('generated_at') or '(not recorded)'}_")
    lines.append("")
    lines.append(f"**query:** {_md_inline(result.get('query') or '')}")
    lines.append("")
    lines.append(f"> {result.get('guardrail') or SHADOW_GUARDRAIL}")
    lines.append("")
    lines.append(f"- anti-lessons considered: {result.get('total_anti_lessons_considered', 0)}")
    lines.append(
        f"- matches shown: {len(matches)} (max_items={result.get('max_items', len(matches))})"
    )
    lines.append(f"- skipped: {len(skipped)}")
    lines.append("")

    lines.append(f"## Top matched anti-lessons ({len(matches)})")
    lines.append("")
    if matches:
        lines.append("| lesson_id | title | score | reasons |")
        lines.append("| --- | --- | --- | --- |")
        for m in matches:
            lines.append(
                "| {id} | {title} | {score} | {reasons} |".format(
                    id=_md_escape_cell(m.get("lesson_id")),
                    title=_md_escape_cell(_truncate(m.get("title", ""))),
                    score=_md_escape_cell(m.get("score")),
                    reasons=_md_escape_cell(", ".join(m.get("reasons", [])) or "—"),
                )
            )
        lines.append("")
        for m in matches:
            heading = _truncate(m.get("title", "") or str(m.get("lesson_id") or "match"))
            lines.append(f"### {_md_escape_cell(heading)}")
            lines.append("")
            lines.append(
                f"- lesson_id: `{m.get('lesson_id')}` (score {m.get('score')}, shadow_only)"
            )
            lines.append(f"- reasons: {', '.join(m.get('reasons', [])) or '—'}")
            if m.get("tempting_wrong_pattern"):
                lines.append(
                    f"- tempting_wrong_pattern: {_md_inline(_truncate(m['tempting_wrong_pattern'], 160))}"
                )
            if m.get("why_wrong"):
                lines.append(f"- why_wrong: {_md_inline(_truncate(m['why_wrong'], 160))}")
            if m.get("safer_alternative"):
                lines.append(
                    f"- safer_alternative: {_md_inline(_truncate(m['safer_alternative'], 160))}"
                )
            lines.append("")
    else:
        lines.append("_No anti-lessons matched this query._")
        lines.append("")

    lines.append("## Blocked actions (enforced — shadow retrieval is report-only)")
    lines.append("")
    for action in BLOCKED_ACTIONS:
        lines.append(f"- `{action}` — not performed")
    lines.append("")
    lines.append(SHADOW_GUARDRAIL)

    return "\n".join(lines).rstrip() + "\n"
