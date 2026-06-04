"""Phase 11.4 — Anti-Lesson Evidence / Reporting Shadow Views.

A *read-only* reporting layer over stored anti-lessons. It summarizes them for
audit/explanation and produces both a structured (JSON-like) dict and a Markdown
view. It changes nothing about live behavior:

  * ``build_anti_lesson_report`` / ``format_anti_lesson_report_markdown`` are
    pure (they take an already-loaded list and never touch the store);
  * ``load_anti_lesson_report`` is the only store-aware entry — it *reads*
    lessons via ``lesson_store.list_lessons`` and never mutates anything;
  * nothing here promotes, blocks, archives, merges, or activates a lesson, and
    nothing calls a model / CONTROL / Dream / patching / benchmark / subprocess /
    Docker / network.

Anti-lessons remain inert (Phase 11.1): this report is shadow visibility only.
Making anti-lessons retrieval-eligible or CONTROL-visible is still deferred.
"""
from __future__ import annotations

from typing import Any

from core import lesson_duplicates, lesson_store
from core.lesson_store import _now_iso, is_anti_lesson


REPORT_TITLE = "Anti-Lesson Report"
GUARDRAIL_NOTE = (
    "Anti-lessons are report-only in this phase. They are not used by active "
    "retrieval or CONTROL prompts."
)

# Required fields for a "complete" anti-lesson. ``title`` is top-level; the rest
# live in the ``candidate`` (evidence) sub-dict.
REQUIRED_ANTI_FIELDS = ("title", "tempting_wrong_pattern", "why_wrong", "safer_alternative")

_TOP_PATTERNS_LIMIT = 10


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


def _record_row(record: dict) -> dict:
    """Compact, display-safe row for one anti-lesson (no raw payload dump)."""
    cand = _candidate(record)
    return {
        "id": record.get("id"),
        "title": _text(record.get("title")),
        "status": record.get("status") or "candidate",
        "scope": _scope_of(record),
        "repo_scope_id": record.get("repo_scope_id"),
        "source": record.get("source"),
        "source_report": record.get("source_report"),
        "tempting_wrong_pattern": _text(cand.get("tempting_wrong_pattern")),
        "why_wrong": _text(cand.get("why_wrong")),
        "safer_alternative": _text(cand.get("safer_alternative")),
        "evidence_refs": _str_list(cand.get("evidence_refs")),
        "related_lesson_ids": _str_list(cand.get("related_lesson_ids")),
        "tags": _str_list(record.get("tags")),
        "duplicate_of": record.get("duplicate_of"),
        "archived": bool(record.get("archived")),
        "superseded_by": record.get("superseded_by"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }


def _missing_required_fields(record: dict) -> list[str]:
    cand = _candidate(record)
    missing: list[str] = []
    if not _text(record.get("title")):
        missing.append("title")
    for field in ("tempting_wrong_pattern", "why_wrong", "safer_alternative"):
        if not _text(cand.get(field)):
            missing.append(field)
    return missing


def build_anti_lesson_report(
    lessons: list[dict],
    *,
    generated_at: str | None = None,
) -> dict:
    """Summarize anti-lessons from an already-loaded ``lessons`` list (pure).

    ``lessons`` may contain both normal and anti-lessons; only anti-lessons are
    summarized, while normal lessons are used solely to resolve
    ``related_lesson_ids`` references for the "related normal lessons" section.

    Returns a structured dict (see keys below). Never reads the store, never
    mutates input records, and never calls a model.
    """
    records = lessons if isinstance(lessons, list) else []
    anti = [r for r in records if isinstance(r, dict) and is_anti_lesson(r)]
    normals_by_id = {
        r.get("id"): r
        for r in records
        if isinstance(r, dict) and not is_anti_lesson(r) and r.get("id")
    }

    by_status = {
        lesson_store.STATUS_CANDIDATE: 0,
        lesson_store.STATUS_ACTIVE: 0,
        lesson_store.STATUS_BLOCKED: 0,
    }
    by_scope = {"global": 0, "repo": 0}
    archived: list[dict] = []
    superseded: list[dict] = []
    duplicate_links: list[dict] = []
    weak_records: list[dict] = []
    related_normal_lessons: list[dict] = []
    pattern_counts: dict[str, dict] = {}

    rows: list[dict] = []
    for record in anti:
        row = _record_row(record)
        rows.append(row)

        status = row["status"]
        if status in by_status:
            by_status[status] += 1
        by_scope[row["scope"]] += 1

        if row["archived"]:
            archived.append({"id": row["id"], "title": row["title"], "status": status})
        if row["superseded_by"]:
            superseded.append({
                "id": row["id"],
                "title": row["title"],
                "superseded_by": row["superseded_by"],
            })
        if row["duplicate_of"]:
            duplicate_links.append({
                "id": row["id"],
                "title": row["title"],
                "duplicate_of": row["duplicate_of"],
            })

        missing = _missing_required_fields(record)
        reasons = [f"missing required field: {f}" for f in missing]
        if not row["evidence_refs"] and not row["related_lesson_ids"]:
            reasons.append("no evidence_refs or related_lesson_ids")
        if missing:
            weak_records.append({
                "id": row["id"],
                "title": row["title"],
                "missing": missing,
                "reasons": reasons,
            })

        for related_id in row["related_lesson_ids"]:
            normal = normals_by_id.get(related_id)
            if normal is not None:
                related_normal_lessons.append({
                    "anti_id": row["id"],
                    "anti_title": row["title"],
                    "related_id": related_id,
                    "related_title": _text(normal.get("title")),
                    "related_status": normal.get("status"),
                })

        pattern = row["tempting_wrong_pattern"]
        if pattern:
            key = " ".join(pattern.lower().split())
            entry = pattern_counts.get(key)
            if entry is None:
                pattern_counts[key] = {"pattern": pattern, "count": 1}
            else:
                entry["count"] += 1

    top_tempting_patterns = sorted(
        pattern_counts.values(),
        key=lambda e: (-e["count"], e["pattern"].lower()),
    )[:_TOP_PATTERNS_LIMIT]

    candidates = [r for r in rows if r["status"] == lesson_store.STATUS_CANDIDATE]
    duplicate_groups = lesson_duplicates.find_duplicate_groups(anti)

    counts = {
        "total": len(anti),
        "by_status": by_status,
        "by_scope": by_scope,
        "by_kind": {lesson_store.KIND_ANTI_LESSON: len(anti)},
        "archived": len(archived),
        "superseded": len(superseded),
        "with_duplicate_of": len(duplicate_links),
        "weak": len(weak_records),
    }

    return {
        "title": REPORT_TITLE,
        "generated_at": generated_at,
        "guardrail": GUARDRAIL_NOTE,
        "counts": counts,
        "records": rows,
        "candidates": candidates,
        "duplicate_groups": duplicate_groups,
        "duplicate_links": duplicate_links,
        "related_normal_lessons": related_normal_lessons,
        "weak_records": weak_records,
        "archived": archived,
        "superseded": superseded,
        "top_tempting_patterns": top_tempting_patterns,
    }


def load_anti_lesson_report(
    *,
    repo_path: str | None = None,
    scope: str | None = None,
    repo_scope_id: str | None = None,
    include_global: bool = True,
    generated_at: str | None = None,
) -> dict:
    """Read lessons from the store and build the anti-lesson report.

    The only store-aware entry point. It performs a single READ
    (``lesson_store.list_lessons``) across all statuses/kinds in the requested
    scope (anti-lessons are summarized; normal lessons resolve related links) and
    delegates to the pure ``build_anti_lesson_report``. It never writes.
    """
    lessons = lesson_store.list_lessons(
        repo_path=repo_path,
        include_global=include_global,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    return build_anti_lesson_report(
        lessons,
        generated_at=generated_at if generated_at is not None else _now_iso(),
    )


def _md_escape_cell(value: Any) -> str:
    text = value if isinstance(value, str) else ("" if value is None else str(value))
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _truncate(text: str, limit: int = 80) -> str:
    text = text.strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def format_anti_lesson_report_markdown(report: dict) -> str:
    """Render an anti-lesson ``report`` dict as Markdown (pure)."""
    if not isinstance(report, dict):
        report = {}
    counts = report.get("counts") or {}
    by_status = counts.get("by_status") or {}
    by_scope = counts.get("by_scope") or {}

    lines: list[str] = []
    lines.append(f"# {report.get('title') or REPORT_TITLE}")
    lines.append("")
    lines.append(f"_generated_at: {report.get('generated_at') or '(not recorded)'}_")
    lines.append("")
    lines.append(f"> {report.get('guardrail') or GUARDRAIL_NOTE}")
    lines.append("")

    lines.append("## Counts")
    lines.append("")
    lines.append(f"- total anti-lessons: {counts.get('total', 0)}")
    lines.append(
        "- by status: "
        f"candidate {by_status.get('candidate', 0)}, "
        f"active {by_status.get('active', 0)}, "
        f"blocked {by_status.get('blocked', 0)}"
    )
    lines.append(
        f"- by scope: global {by_scope.get('global', 0)}, repo {by_scope.get('repo', 0)}"
    )
    lines.append(
        f"- archived: {counts.get('archived', 0)} · "
        f"superseded: {counts.get('superseded', 0)} · "
        f"with duplicate_of: {counts.get('with_duplicate_of', 0)} · "
        f"weak/incomplete: {counts.get('weak', 0)}"
    )
    lines.append("")

    candidates = report.get("candidates") or []
    lines.append(f"## Candidate anti-lessons ({len(candidates)})")
    lines.append("")
    if candidates:
        lines.append("| id | title | scope | tempting_wrong_pattern | evidence | related |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in candidates:
            scope = row.get("scope", "global")
            if scope == "repo" and row.get("repo_scope_id"):
                scope = f"repo:{row['repo_scope_id']}"
            lines.append(
                "| {id} | {title} | {scope} | {pattern} | {evidence} | {related} |".format(
                    id=_md_escape_cell(row.get("id")),
                    title=_md_escape_cell(_truncate(row.get("title", ""))),
                    scope=_md_escape_cell(scope),
                    pattern=_md_escape_cell(_truncate(row.get("tempting_wrong_pattern", ""))),
                    evidence=_md_escape_cell(", ".join(row.get("evidence_refs", [])) or "—"),
                    related=_md_escape_cell(", ".join(row.get("related_lesson_ids", [])) or "—"),
                )
            )
    else:
        lines.append("_No candidate anti-lessons._")
    lines.append("")

    duplicate_groups = report.get("duplicate_groups") or []
    duplicate_links = report.get("duplicate_links") or []
    lines.append("## Duplicate warnings")
    lines.append("")
    if not duplicate_groups and not duplicate_links:
        lines.append("_No duplicate signals detected._")
    else:
        for link in duplicate_links:
            lines.append(
                f"- `{link.get('id')}` is marked duplicate_of `{link.get('duplicate_of')}`"
            )
        for group in duplicate_groups:
            ids = ", ".join(f"`{i}`" for i in group.get("lesson_ids", []))
            reasons = "; ".join(group.get("hint_reasons", []))
            lines.append(f"- group: {ids} — {reasons}")
    lines.append("")

    related = report.get("related_normal_lessons") or []
    if related:
        lines.append("## Related normal lessons")
        lines.append("")
        for rel in related:
            lines.append(
                f"- anti `{rel.get('anti_id')}` → normal `{rel.get('related_id')}`"
                f" ({_md_escape_cell(_truncate(rel.get('related_title', '') or '', 60))})"
            )
        lines.append("")

    weak = report.get("weak_records") or []
    lines.append(f"## Weak / incomplete records ({len(weak)})")
    lines.append("")
    if weak:
        for entry in weak:
            reasons = "; ".join(entry.get("reasons", []) or entry.get("missing", []))
            lines.append(f"- `{entry.get('id')}`: {reasons}")
    else:
        lines.append("_No weak or incomplete records._")
    lines.append("")

    top = report.get("top_tempting_patterns") or []
    if top:
        lines.append("## Top tempting_wrong_pattern values")
        lines.append("")
        for entry in top:
            lines.append(
                f"- ({entry.get('count')}×) {_md_escape_cell(_truncate(entry.get('pattern', '')))}"
            )
        lines.append("")

    archived = report.get("archived") or []
    superseded = report.get("superseded") or []
    if archived or superseded:
        lines.append("## Archived / superseded (non-live metadata)")
        lines.append("")
        for entry in archived:
            lines.append(f"- archived: `{entry.get('id')}` — {_md_escape_cell(entry.get('title', ''))}")
        for entry in superseded:
            lines.append(
                f"- superseded: `{entry.get('id')}` → `{entry.get('superseded_by')}`"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
