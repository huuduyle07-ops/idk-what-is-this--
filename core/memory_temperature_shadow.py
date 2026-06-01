"""Phase 13.7 - Memory Temperature shadow retrieval report.

This module is read-only and accepts already-loaded lesson records. It computes
what a temperature-adjusted lesson order would look like without changing live
lesson retrieval, CONTROL prompt content, ranking, storage, patching,
validation, benchmark scoring, model/API calls, DB writes, or subprocess
lifecycle behavior.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.memory_temperature import (
    MEMORY_TEMPERATURE_GUARDRAIL,
    MemoryTemperature,
    classify_memory_temperature,
)


MEMORY_TEMPERATURE_SHADOW_GUARDRAIL = (
    "Memory Temperature Shadow Retrieval is report/debug-only. It does not "
    "change lesson retrieval order, CONTROL prompts, live ranking, lesson "
    "storage, patching, validation, benchmark scoring, model/API calls, DB "
    "writes, or subprocess/Docker behavior."
)

_BAND_RANK = {"hot": 0, "warm": 1, "cold": 2}
_MAX_REASONS = 4


def apply_shadow_temperature_order(lessons, now=None) -> list[dict[str, Any]]:
    """Return the temperature-adjusted order for reporting only.

    Frozen/audit-only records are excluded from this shadow order and remain
    visible in :func:`build_shadow_retrieval_report` as blocked rows. Cold
    records stay eligible, just sorted after warmer records.
    """
    rows = _build_rows(lessons, now=now)
    return _eligible_shadow_rows(rows)


def build_shadow_retrieval_report(lessons, now=None, limit=None) -> dict[str, Any]:
    """Build a JSON-safe shadow retrieval report over already-loaded lessons."""
    rows = _build_rows(lessons, now=now)
    shadow_rows = _eligible_shadow_rows(rows)
    if limit is not None:
        shadow_rows = shadow_rows[:_coerce_limit(limit)]

    shadow_rank_by_original_rank = {
        row["original_rank"]: rank for rank, row in enumerate(shadow_rows, start=1)
    }

    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        shadow_rank = shadow_rank_by_original_rank.get(item["original_rank"])
        item["shadow_rank"] = shadow_rank
        item["rank_delta"] = (
            item["original_rank"] - shadow_rank if shadow_rank is not None else None
        )
        items.append(item)

    return {
        "ok": True,
        "mode": "shadow",
        "count": len(items),
        "limit": limit,
        "original_order": [item["item_id"] for item in rows],
        "shadow_order": [item["item_id"] for item in shadow_rows],
        "excluded_order": [item["item_id"] for item in rows if item["excluded"]],
        "items": items,
        "guardrail": MEMORY_TEMPERATURE_SHADOW_GUARDRAIL,
        "classifier_guardrail": MEMORY_TEMPERATURE_GUARDRAIL,
    }


def format_shadow_retrieval_markdown(report) -> str:
    """Render a shadow retrieval report as Markdown."""
    data = report if isinstance(report, Mapping) else {}
    items = list(data.get("items") or [])

    lines: list[str] = []
    lines.append("# Memory Temperature Shadow Retrieval")
    lines.append("")
    lines.append(
        "> Shadow mode only: actual lesson retrieval order and CONTROL prompt "
        "content are unchanged."
    )
    lines.append("")
    lines.append(
        "| item_id | original_rank | shadow_rank | rank_delta | "
        "temperature_band | temperature | excluded | reason |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    if not items:
        lines.append("| _(no lessons)_ | - | - | - | - | - | - | - |")
    else:
        for item in items:
            lines.append(
                "| {item_id} | {original_rank} | {shadow_rank} | {rank_delta} | "
                "{band} | {temperature:.2f} | {excluded} | {reason} |".format(
                    item_id=_md_cell(item.get("item_id")),
                    original_rank=item.get("original_rank") or "-",
                    shadow_rank=item.get("shadow_rank")
                    if item.get("shadow_rank") is not None
                    else "-",
                    rank_delta=item.get("rank_delta")
                    if item.get("rank_delta") is not None
                    else "-",
                    band=_md_cell(item.get("temperature_band")),
                    temperature=_coerce_float(item.get("temperature")),
                    excluded="yes" if item.get("excluded") else "no",
                    reason=_md_cell(item.get("reason") or "-"),
                )
            )
    lines.append("")
    lines.append(f"> {data.get('guardrail') or MEMORY_TEMPERATURE_SHADOW_GUARDRAIL}")
    lines.append("")
    return "\n".join(lines)


def _build_rows(lessons, now=None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, lesson in enumerate(list(lessons or []), start=1):
        temperature = classify_memory_temperature(lesson, now=now)
        excluded, exclude_reason = _excluded_reason(temperature)
        rows.append(
            {
                "item_id": temperature.item_id,
                "title": _lesson_title(lesson),
                "original_rank": index,
                "shadow_rank": None,
                "rank_delta": None,
                "temperature": temperature.temperature,
                "temperature_band": temperature.band,
                "should_surface": temperature.should_surface,
                "excluded": excluded,
                "blocked": excluded,
                "exclude_reason": exclude_reason,
                "reason": _reason_text(temperature, exclude_reason),
                "warnings": list(temperature.warnings),
            }
        )
    return rows


def _eligible_shadow_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [row for row in rows if not row["excluded"]]
    return sorted(
        eligible,
        key=lambda row: (
            _BAND_RANK.get(str(row.get("temperature_band") or ""), 9),
            -_coerce_float(row.get("temperature")),
            row["original_rank"],
        ),
    )


def _excluded_reason(temperature: MemoryTemperature) -> tuple[bool, str]:
    if temperature.band != "frozen":
        return False, ""
    for reason in temperature.reasons:
        if "hard freeze:" in reason:
            return True, reason.split("hard freeze:", 1)[1].strip()
    return True, "frozen"


def _reason_text(temperature: MemoryTemperature, exclude_reason: str) -> str:
    reasons = list(temperature.reasons)[:_MAX_REASONS]
    if exclude_reason:
        reasons.append(f"excluded from shadow order: {exclude_reason}")
    return "; ".join(reasons) if reasons else "-"


def _lesson_title(lesson) -> str:
    if isinstance(lesson, Mapping):
        title = lesson.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return ""


def _coerce_limit(value) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, limit)


def _coerce_float(value) -> float:
    try:
        if value is None or isinstance(value, bool):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _md_cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()
