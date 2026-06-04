"""Phase 11.7b — Default-Off CONTROL Anti-Lesson Preview Report.

Combines the anti-lesson *shadow retrieval* (11.6) and the anti-lesson CONTROL
*block preview* (11.7a) into a single read-only report that can be shown *beside*
real CONTROL/debug context — **without appending anything to the actual CONTROL
prompt**:

  * ``build_anti_lesson_control_preview_report`` / ``format_..._markdown`` are pure
    (they take an already-loaded list and never touch the store);
  * ``load_anti_lesson_control_preview_report`` is the only store-aware entry — it
    *reads* lessons and never mutates anything;
  * nothing here injects into CONTROL, calls ``build_control_prompt``, modifies
    active retrieval, runs Dream / the mutation oracle / benchmarks / patching / a
    model, and nothing creates/promotes/blocks/merges a lesson.

The report makes the comparison explicit: the actual CONTROL prompt is *unchanged*
and anti-lessons are *not injected*. This is the read-only precursor to a future,
default-off injection flag (11.7c).
"""
from __future__ import annotations

from typing import Any

from core import anti_lesson_prompt_preview, anti_lesson_retrieval_shadow, lesson_store
from core.anti_lesson_prompt_preview import build_anti_lesson_control_block_preview
from core.anti_lesson_retrieval_shadow import (
    build_anti_lesson_shadow_retrieval,
    is_anti_lesson,
)
from core.lesson_store import _now_iso


REPORT_TITLE = "Anti-Lesson CONTROL Preview Report"
REPORT_GUARDRAIL = (
    "Report only. The actual CONTROL prompt is unchanged."
)
CONTROL_UNCHANGED_STATEMENT = "This report does not modify build_control_prompt output."
NOT_INJECTED_STATEMENT = "Anti-lessons are not injected into CONTROL in this phase."

# Same contract as the underlying shadow / preview layers.
BLOCKED_ACTIONS = anti_lesson_prompt_preview.BLOCKED_ACTIONS

_DEFAULT_MAX_ITEMS = 3
_MAX_ITEMS_CAP = 50
# Pull a generous shadow match set so the preview block can choose freely from it.
_SHADOW_POOL = 50


def _clamp_max_items(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_ITEMS
    return max(1, min(n, _MAX_ITEMS_CAP))


def build_anti_lesson_control_preview_report(
    query: str,
    records: list[dict],
    *,
    context: dict | None = None,
    max_items: int = _DEFAULT_MAX_ITEMS,
    generated_at: str | None = None,
) -> dict:
    """Build a read-only CONTROL preview *report* from an already-loaded list.

    Runs the pure shadow matcher and the pure preview-block builder, then assembles
    a report that states plainly that the actual CONTROL prompt is unchanged and
    anti-lessons are not injected. Pure — never reads the store, never mutates
    input, never calls a model, never executes anything, and never calls
    ``build_control_prompt``.
    """
    max_n = _clamp_max_items(max_items)
    q = query if isinstance(query, str) else ""

    shadow = build_anti_lesson_shadow_retrieval(
        q,
        records,
        context=context,
        max_items=_SHADOW_POOL,
        generated_at=generated_at,
    )
    preview = build_anti_lesson_control_block_preview(shadow, max_items=max_n)

    return {
        "title": REPORT_TITLE,
        "generated_at": generated_at,
        "query": q,
        "guardrail": REPORT_GUARDRAIL,
        # Explicit comparison: live behavior is untouched.
        "control_prompt_status": "unchanged",
        "anti_lesson_injection": "not_injected",
        "notes": [CONTROL_UNCHANGED_STATEMENT, NOT_INJECTED_STATEMENT],
        "max_items": max_n,
        "context_provided": isinstance(context, dict) and bool(context),
        "shadow_retrieval": shadow,
        "preview_block": preview,
        "blocked_actions": list(BLOCKED_ACTIONS),
        # Always true: this layer is display-only.
        "report_only": True,
    }


def load_anti_lesson_control_preview_report(
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
    """Read lessons from the store and build a CONTROL preview report.

    The only store-aware entry point. It performs a single READ
    (``lesson_store.list_lessons``), keeps only ``kind="anti_lesson"`` records, and
    delegates to the pure builder. It never writes and never calls
    ``build_control_prompt``.
    """
    lessons = lesson_store.list_lessons(
        repo_path=repo_path,
        include_global=include_global,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    anti = [r for r in lessons if is_anti_lesson(r)]
    return build_anti_lesson_control_preview_report(
        query,
        anti,
        context=context,
        max_items=max_items,
        generated_at=generated_at if generated_at is not None else _now_iso(),
    )


# ── Markdown ─────────────────────────────────────────────────────────────────


def _md_inline(value: Any) -> str:
    text = value if isinstance(value, str) else ("" if value is None else str(value))
    return " ".join(text.split())


def _md_escape_cell(value: Any) -> str:
    text = value if isinstance(value, str) else ("" if value is None else str(value))
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _truncate(text: str, limit: int = 80) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def format_anti_lesson_control_preview_report_markdown(report: dict) -> str:
    """Render a CONTROL preview ``report`` dict as Markdown (pure)."""
    if not isinstance(report, dict):
        report = {}
    shadow = report.get("shadow_retrieval") or {}
    preview = report.get("preview_block") or {}
    matches = [m for m in (shadow.get("selected_matches") or []) if isinstance(m, dict)]
    items = [i for i in (preview.get("items") or []) if isinstance(i, dict)]

    lines: list[str] = []
    lines.append(f"# {report.get('title') or REPORT_TITLE}")
    lines.append("")
    lines.append(f"_generated_at: {report.get('generated_at') or '(not recorded)'}_")
    lines.append("")
    lines.append(f"**query:** {_md_inline(report.get('query') or '')}")
    lines.append("")
    lines.append(f"> {report.get('guardrail') or REPORT_GUARDRAIL}")
    lines.append("")

    # Explicit comparison.
    lines.append("## CONTROL vs anti-lesson preview")
    lines.append("")
    lines.append("| surface | status |")
    lines.append("| --- | --- |")
    lines.append(f"| actual CONTROL prompt | {report.get('control_prompt_status', 'unchanged')} |")
    lines.append(f"| anti-lesson block | preview-only, {report.get('anti_lesson_injection', 'not_injected')} |")
    lines.append("")
    for note in report.get("notes") or (CONTROL_UNCHANGED_STATEMENT, NOT_INJECTED_STATEMENT):
        lines.append(f"- {note}")
    lines.append("")

    # Shadow matches.
    lines.append(f"## Selected anti-lessons ({len(matches)})")
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
    else:
        lines.append("_No anti-lessons matched this query._")
        lines.append("")

    # Preview block (reuse the 11.7a formatter verbatim).
    lines.append(f"## Anti-lesson CONTROL block (preview, {len(items)} item(s))")
    lines.append("")
    block_md = anti_lesson_prompt_preview.format_anti_lesson_control_block_markdown(preview)
    lines.append(block_md.rstrip())
    lines.append("")

    # Blocked actions.
    lines.append("## Blocked actions (enforced — report only)")
    lines.append("")
    for action in report.get("blocked_actions") or BLOCKED_ACTIONS:
        lines.append(f"- `{action}` — not performed")
    lines.append("")
    lines.append(CONTROL_UNCHANGED_STATEMENT)
    lines.append("")
    lines.append(NOT_INJECTED_STATEMENT)

    return "\n".join(lines).rstrip() + "\n"
