"""Phase 11.7a — Anti-Lesson CONTROL Block Formatter (pure preview only).

A *pure* formatter that shows what an anti-lesson CONTROL block *would* look like
if anti-lessons were enabled later — and changes nothing about live behavior:

  * ``build_anti_lesson_control_block_preview`` / ``format_..._markdown`` are pure
    (they take an already-built shadow-retrieval result dict and never touch the
    store);
  * nothing here injects into CONTROL, calls ``build_control_prompt``, modifies
    active retrieval, runs Dream / the mutation oracle / benchmarks / patching / a
    model, and nothing creates/promotes/blocks/merges a lesson.

Every produced item is flagged ``shadow_only`` and the preview carries an explicit
``PREVIEW ONLY / NOT INJECTED INTO CONTROL`` label plus a ``blocked_actions`` list
making the contract unmistakable.

This is the read-only precursor to a *future*, default-off CONTROL integration.
"""
from __future__ import annotations

from typing import Any


PREVIEW_TITLE = "Anti-Lesson CONTROL Block (preview)"
PREVIEW_LABEL = "PREVIEW ONLY / NOT INJECTED INTO CONTROL"
PREVIEW_GUARDRAIL = (
    "Preview only. This block is not injected into CONTROL, active retrieval, "
    "patching, Dream, benchmarks, or any model call."
)

# Mirrors the shadow-retrieval contract; the preview adds nothing executable.
BLOCKED_ACTIONS = (
    "inject_into_control",
    "modify_active_retrieval",
    "patch",
    "benchmark",
    "dream",
    "model_call",
    "promote",
)

_DEFAULT_MAX_ITEMS = 3
_MAX_ITEMS_CAP = 50


# ── small pure helpers ───────────────────────────────────────────────────────


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def _clamp_max_items(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_ITEMS
    return max(1, min(n, _MAX_ITEMS_CAP))


def _preview_item(match: dict) -> dict:
    """Project one shadow ``selected_matches`` row into a CONTROL-block item."""
    if not isinstance(match, dict):
        match = {}
    return {
        "lesson_id": match.get("lesson_id"),
        "title": _text(match.get("title")),
        "tempting_wrong_pattern": _text(match.get("tempting_wrong_pattern")),
        "why_wrong": _text(match.get("why_wrong")),
        "safer_alternative": _text(match.get("safer_alternative")),
        "evidence_refs": _str_list(match.get("evidence_refs")),
        "duplicate_of": match.get("duplicate_of"),
        # Always true: a preview never feeds the live agent path.
        "shadow_only": True,
    }


def build_anti_lesson_control_block_preview(
    shadow_result: dict,
    *,
    max_items: int = _DEFAULT_MAX_ITEMS,
) -> dict:
    """Build a *preview* of the anti-lesson CONTROL block from a shadow result.

    ``shadow_result`` is the dict returned by
    ``anti_lesson_retrieval_shadow.build_anti_lesson_shadow_retrieval`` /
    ``load_anti_lesson_shadow_retrieval``. Pure — never reads the store, never
    mutates input, never calls a model, never executes anything. The result is for
    display only; see the module docstring for the safety contract.
    """
    src = shadow_result if isinstance(shadow_result, dict) else {}
    matches = [m for m in (src.get("selected_matches") or []) if isinstance(m, dict)]

    max_n = _clamp_max_items(max_items)
    items = [_preview_item(m) for m in matches[:max_n]]

    return {
        "title": PREVIEW_TITLE,
        "generated_at": src.get("generated_at"),
        "query": src.get("query") or "",
        "label": PREVIEW_LABEL,
        "guardrail": PREVIEW_GUARDRAIL,
        "max_items": max_n,
        "source_total_matches": len(matches),
        "items": items,
        "blocked_actions": list(BLOCKED_ACTIONS),
        # Always true: this layer is display-only.
        "preview_only": True,
    }


# ── Markdown ─────────────────────────────────────────────────────────────────


def _md_inline(value: Any) -> str:
    text = value if isinstance(value, str) else ("" if value is None else str(value))
    return " ".join(text.split())


def _truncate(text: str, limit: int = 200) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def format_anti_lesson_control_block_markdown(preview: dict) -> str:
    """Render a ``preview`` dict as Markdown (pure)."""
    if not isinstance(preview, dict):
        preview = {}
    items = [i for i in (preview.get("items") or []) if isinstance(i, dict)]

    lines: list[str] = []
    lines.append(f"# {preview.get('title') or PREVIEW_TITLE}")
    lines.append("")
    lines.append(f"**{preview.get('label') or PREVIEW_LABEL}**")
    lines.append("")
    lines.append(f"_generated_at: {preview.get('generated_at') or '(not recorded)'}_")
    lines.append("")
    lines.append(f"**query:** {_md_inline(preview.get('query') or '')}")
    lines.append("")
    lines.append(f"> {preview.get('guardrail') or PREVIEW_GUARDRAIL}")
    lines.append("")
    lines.append(
        f"- block items: {len(items)} (max_items={preview.get('max_items', len(items))})"
    )
    lines.append(f"- source matches: {preview.get('source_total_matches', len(items))}")
    lines.append("")

    lines.append("## Anti-lesson CONTROL block (preview)")
    lines.append("")
    if items:
        for idx, item in enumerate(items, start=1):
            heading = _truncate(item.get("title", "") or str(item.get("lesson_id") or "item"), 80)
            lines.append(f"### {idx}. {heading}")
            lines.append("")
            lines.append(f"- lesson_id: `{item.get('lesson_id')}` (shadow_only, preview only)")
            if item.get("tempting_wrong_pattern"):
                lines.append(
                    f"- ❌ tempting_wrong_pattern: {_md_inline(_truncate(item['tempting_wrong_pattern']))}"
                )
            if item.get("why_wrong"):
                lines.append(f"- ⚠️ why_wrong: {_md_inline(_truncate(item['why_wrong']))}")
            if item.get("safer_alternative"):
                lines.append(
                    f"- ✅ safer_alternative: {_md_inline(_truncate(item['safer_alternative']))}"
                )
            if item.get("evidence_refs"):
                lines.append(f"- evidence_refs: {', '.join(item['evidence_refs'])}")
            if item.get("duplicate_of"):
                lines.append(f"- duplicate_of: `{item['duplicate_of']}`")
            lines.append("")
    else:
        lines.append("_No anti-lessons matched — the preview block would be empty._")
        lines.append("")

    lines.append("## Blocked actions (enforced — this is a preview)")
    lines.append("")
    for action in preview.get("blocked_actions") or BLOCKED_ACTIONS:
        lines.append(f"- `{action}` — not performed")
    lines.append("")
    lines.append(PREVIEW_GUARDRAIL)

    return "\n".join(lines).rstrip() + "\n"
