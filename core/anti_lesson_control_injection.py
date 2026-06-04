"""Phase 11.7c — Default-Off CONTROL Anti-Lesson Injection (two-key gate).

The FIRST behavior-changing anti-lesson slice. It builds an
``[ANTI-LESSONS / DO NOT REPEAT — EXPERIMENTAL]`` block for the CONTROL prompt,
but ONLY when BOTH keys are turned:

  1. ``config.ANTI_LESSONS_CONTROL_ENABLED`` is true (server flag, default off),
     AND
  2. the specific request explicitly passes ``requested=True``.

If either key is missing the function returns ``""`` so ``build_control_prompt``
output is byte-identical to Phase 11.7b. The block is built read-only from the
11.6 shadow retrieval + the 11.7a preview builder. Nothing here:

  * promotes / creates / blocks / merges / mutates a lesson;
  * makes anti-lessons active-retrieval eligible (that stays governed by
    ``ANTI_LESSONS_ENABLED``, independent of this flag);
  * runs Dream / the mutation oracle / benchmarks / patching / a model;
  * touches the network, a subprocess, or Docker.

Per-run only: there is no global toggle and no saved setting. The optional
``summarize_anti_lesson_control_injection`` returns the *only* metadata shape a
runner/session may record — ``requested`` / ``enabled_by_config`` / ``injected``
/ ``selected_count`` — and never a global preference.
"""
from __future__ import annotations

from typing import Any

from core.anti_lesson_prompt_preview import build_anti_lesson_control_block_preview
from core.anti_lesson_retrieval_shadow import load_anti_lesson_shadow_retrieval


ANTI_LESSON_CONTROL_HEADER = "[ANTI-LESSONS / DO NOT REPEAT — EXPERIMENTAL]"
ANTI_LESSON_CONTROL_INTRO = (
    "These are warnings about tempting but wrong patterns. Use them only to "
    "avoid repeating known bad fixes."
)

# Small by design: default 1–3 items, hard cap 5 even if a caller asks for more.
_DEFAULT_MAX_ITEMS = 3
_HARD_CAP = 5
# Pull a generous ranked pool so the (small) block can choose the best matches.
_SHADOW_POOL = 50


def _config_enabled() -> bool:
    """Read the server flag fail-closed (default off, never raises)."""
    try:
        import config as _config
    except Exception:
        return False
    return bool(getattr(_config, "ANTI_LESSONS_CONTROL_ENABLED", False))


def _clamp_max_items(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_ITEMS
    return max(1, min(n, _HARD_CAP))


def _select_items(repo_path: str | None, user_query: str, *, max_items: int) -> list[dict]:
    """Read anti-lessons and project them into bounded preview items (read-only)."""
    cap = _clamp_max_items(max_items)
    shadow = load_anti_lesson_shadow_retrieval(
        user_query if isinstance(user_query, str) else "",
        repo_path=repo_path,
        max_items=max(cap, _SHADOW_POOL),
    )
    preview = build_anti_lesson_control_block_preview(shadow, max_items=cap)
    return [i for i in (preview.get("items") or []) if isinstance(i, dict)]


def _format_block(items: list[dict]) -> str:
    """Render the experimental anti-lesson block (pure)."""
    lines: list[str] = ["", ANTI_LESSON_CONTROL_HEADER, ANTI_LESSON_CONTROL_INTRO, ""]
    for idx, item in enumerate(items, start=1):
        heading = (item.get("title") or str(item.get("lesson_id") or "anti-lesson")).strip()
        lines.append(f"{idx}. {heading}")
        if item.get("tempting_wrong_pattern"):
            lines.append(f"   - tempting_wrong_pattern: {item['tempting_wrong_pattern']}")
        if item.get("why_wrong"):
            lines.append(f"   - why_wrong: {item['why_wrong']}")
        if item.get("safer_alternative"):
            lines.append(f"   - safer_alternative: {item['safer_alternative']}")
        refs = item.get("evidence_refs") or []
        if refs:
            lines.append(f"   - evidence_refs: {', '.join(refs)}")
        lines.append("")
    # Leading newline preserved so the block separates cleanly from prior context.
    return "\n".join(lines).rstrip() + "\n"


def build_anti_lesson_control_block(
    repo_path: str | None,
    user_query: str,
    *,
    requested: bool = False,
    max_items: int = _DEFAULT_MAX_ITEMS,
) -> str:
    """Return the anti-lesson CONTROL block, or ``""`` unless BOTH keys are set.

    Two-key gate (fail-closed): ``requested`` must be true AND
    ``config.ANTI_LESSONS_CONTROL_ENABLED`` must be true. Any disabled key, an
    empty match set, or an unexpected error yields ``""`` so the CONTROL prompt
    stays byte-identical to Phase 11.7b. Read-only: never mutates the store,
    never promotes, never calls a model.
    """
    if not requested:
        return ""
    if not _config_enabled():
        return ""
    try:
        items = _select_items(repo_path, user_query, max_items=max_items)
    except Exception:
        # Fail closed: anti-lessons are advisory; never break the patch flow.
        return ""
    if not items:
        return ""
    return _format_block(items)


def summarize_anti_lesson_control_injection(
    repo_path: str | None,
    user_query: str,
    *,
    requested: bool = False,
    max_items: int = _DEFAULT_MAX_ITEMS,
) -> dict:
    """Return per-run metadata only — never a global preference.

    This is the *only* shape a runner/session may persist for this feature:
    ``requested`` / ``enabled_by_config`` / ``injected`` / ``selected_count``.
    Read-only and fail-closed.
    """
    enabled = _config_enabled()
    count = 0
    if requested and enabled:
        try:
            count = len(_select_items(repo_path, user_query, max_items=max_items))
        except Exception:
            count = 0
    return {
        "requested": bool(requested),
        "enabled_by_config": bool(enabled),
        "injected": bool(requested and enabled and count > 0),
        "selected_count": count,
    }
