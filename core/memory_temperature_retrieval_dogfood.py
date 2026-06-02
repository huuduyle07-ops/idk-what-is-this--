"""Phase 13.10 - Memory Temperature tie-breaker dogfood report (evidence-only).

Given a caller-supplied, already-ordered list of lesson candidates, this layer
produces an *evidence-only* report showing what the (default-off) Memory
Temperature tie-breaker from Phase 13.9 *would* do to their ordering: original
vs adjusted rank, rank delta, the preserved relevance score, the thermal band /
score, whether a tie-break was applied, the reason, and how
frozen / audit-only / blocked lessons are handled.

It is dogfood / explain-only and deterministic. It:

  * accepts candidates passed in by the caller and never queries
    ``lesson_store`` or the DB;
  * never wires into live lesson retrieval and never touches the CONTROL prompt;
  * never enables ``MEMORY_TEMPERATURE_RETRIEVAL_ENABLED`` (the live harness
    control defaults to false / off and this dogfood never sets it) - the ``enabled``
    parameter here only drives the *simulation* shown in the report;
  * never hard-filters cold lessons and never revives or surfaces
    frozen / audit-only / blocked lessons;
  * never mutates the caller's candidates.

It performs no model/API calls, no DB writes, no patch generation, no
validation / benchmark execution, and no subprocess / Docker lifecycle.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.memory_temperature import classify_memory_temperature
from core.memory_temperature_retrieval import (
    TIEBREAK_METADATA_KEY,
    apply_memory_temperature_tiebreaker,
)


SCHEMA_VERSION = 1

MEMORY_TEMPERATURE_TIEBREAKER_DOGFOOD_GUARDRAIL = (
    "Memory Temperature tie-breaker dogfood is evidence-only. It shows what the "
    "default-off tie-breaker would do to a caller-supplied candidate list; it "
    "does not change live lesson retrieval order, the CONTROL prompt, ranking, "
    "patch generation, validation, benchmark scoring, or storage behavior. It "
    "never enables MEMORY_TEMPERATURE_RETRIEVAL_ENABLED, never hard-filters cold "
    "lessons, and never revives frozen / audit-only / blocked lessons."
)


def build_memory_temperature_tiebreaker_dogfood(
    candidates,
    now=None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Build the evidence-only tie-breaker dogfood report (no disk writes).

    ``candidates`` is the caller-supplied, already-ordered list of lesson
    candidates (the final retrieval ordering). The report records both the
    default-off pass-through order (proving live behavior is unchanged) and the
    *simulated* tie-break order when ``enabled`` is true.
    """
    items = list(candidates or [])

    # Default-off pass-through: this is exactly what live retrieval still does.
    passthrough = apply_memory_temperature_tiebreaker(items, enabled=False, now=now)
    default_off_order = [_item_id(c, index) for index, c in enumerate(passthrough)]
    passthrough_unchanged = default_off_order == [
        _item_id(c, index) for index, c in enumerate(items)
    ]

    # Simulated tie-break ordering (does NOT affect live retrieval).
    simulated = apply_memory_temperature_tiebreaker(
        items, enabled=enabled, tiebreak_only=True, now=now
    )

    rows = [_build_row(candidate, index, now=now) for index, candidate in enumerate(simulated)]
    rows.sort(key=lambda row: row["original_rank"])

    return {
        "schema_version": SCHEMA_VERSION,
        "title": "Memory Temperature Tie-breaker Dogfood (Phase 13.10)",
        "candidate_count": len(items),
        "enabled": bool(enabled),
        "default_off_passthrough_unchanged": passthrough_unchanged,
        "default_off_order": default_off_order,
        "live_retrieval_unchanged": True,
        "control_prompt_unchanged": True,
        "harness_flag_enabled": False,
        "harness_flag_wired": True,
        "evidence_only": True,
        "rows": rows,
        "guardrail": MEMORY_TEMPERATURE_TIEBREAKER_DOGFOOD_GUARDRAIL,
    }


def format_memory_temperature_tiebreaker_dogfood_markdown(report: dict[str, Any]) -> str:
    """Render the dogfood ``report`` as Markdown (pure formatting, no I/O)."""
    rows = report.get("rows") or []
    lines = [
        f"# {_cell(report.get('title'))}",
        "",
        "## Summary",
        "",
        f"- Candidate count: `{_cell(report.get('candidate_count'))}`",
        f"- Tie-break simulation enabled: `{_bool(report.get('enabled'))}`",
        f"- Default-off pass-through unchanged: "
        f"`{_bool(report.get('default_off_passthrough_unchanged'))}`",
        f"- Default-off order: {_cell(', '.join(report.get('default_off_order') or []))}",
        "",
        "## Guarantees",
        "",
        "- This is an evidence-only dogfood report.",
        "- Live retrieval is unchanged.",
        "- CONTROL prompt is unchanged.",
        "- `MEMORY_TEMPERATURE_RETRIEVAL_ENABLED` is off by default "
        "(an opt-in editable toggle; this dogfood never enables it).",
        "- Cold lessons are never hard-filtered; frozen / audit-only / blocked "
        "lessons are never revived or surfaced.",
        "",
        "## Per-candidate tie-break preview",
        "",
        "| item_id | original_rank | adjusted_rank | rank_delta | score "
        "| temperature_band | temperature_score | tie_break_applied "
        "| excluded_from_control | reason |",
        "|---|---:|---:|---:|---:|---|---:|---|---|---|",
    ]
    if not rows:
        lines.append("| _(no candidates)_ |  |  |  |  |  |  |  |  |  |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(row.get("item_id")),
                    _cell(row.get("original_rank")),
                    _cell(row.get("adjusted_rank")),
                    _delta(row.get("rank_delta")),
                    _num(row.get("score")),
                    _cell(row.get("temperature_band")),
                    _num(row.get("temperature_score")),
                    _bool(row.get("tie_break_applied")),
                    _bool(row.get("excluded_from_control")),
                    _cell(row.get("reason")),
                ]
            )
            + " |"
        )
    lines += [
        "",
        "## Guardrail",
        "",
        f"> {report.get('guardrail', '')}",
        "",
    ]
    return "\n".join(lines)


# --- internals -------------------------------------------------------------


def _build_row(candidate, position: int, now) -> dict[str, Any]:
    meta = candidate.get(TIEBREAK_METADATA_KEY) if isinstance(candidate, Mapping) else None
    classification = classify_memory_temperature(candidate, now=now)
    band = getattr(classification, "band", "")
    should_surface = bool(getattr(classification, "should_surface", True))

    if isinstance(meta, Mapping):
        original_rank = int(meta.get("original_rank", position + 1))
        adjusted_rank = int(meta.get("adjusted_rank", position + 1))
        temperature_band = meta.get("temperature_band", band)
        temperature_score = meta.get("temperature_score", getattr(classification, "temperature", 0.0))
        tie_break_applied = bool(meta.get("tie_break_applied", False))
        reason = meta.get("reason", "")
    else:
        # Default-off (or non-mapping) candidate: position is the live order.
        original_rank = position + 1
        adjusted_rank = position + 1
        temperature_band = band
        temperature_score = getattr(classification, "temperature", 0.0)
        tie_break_applied = False
        reason = f"rank {original_rank} preserved; band '{band or 'unknown'}'"

    # Only frozen / audit-only / blocked lessons are excluded from CONTROL.
    # Cold lessons are *never* hard-filtered here - they merely lose priority
    # inside a near-equal group - so a cold band does not flag exclusion even
    # though the classifier's surfacing heuristic sets should_surface=False.
    excluded_from_control = temperature_band == "frozen"

    return {
        "item_id": _item_id(candidate, position),
        "original_rank": original_rank,
        "adjusted_rank": adjusted_rank,
        "rank_delta": original_rank - adjusted_rank,
        "score": _score_of(candidate),
        "temperature_band": temperature_band,
        "temperature_score": temperature_score,
        "tie_break_applied": tie_break_applied,
        "should_surface": should_surface,
        "excluded_from_control": bool(excluded_from_control),
        "status": _field(candidate, "status"),
        "reason": reason,
    }


def _item_id(candidate, position: int) -> str:
    if isinstance(candidate, Mapping):
        for key in ("id", "item_id", "note_id", "lesson_id", "title"):
            value = candidate.get(key)
            if value not in (None, ""):
                return str(value)
    return f"candidate-{position + 1}"


def _score_of(candidate) -> float:
    if isinstance(candidate, Mapping):
        value = candidate.get("score")
        try:
            if value is None or isinstance(value, bool):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _field(candidate, key: str):
    if isinstance(candidate, Mapping):
        return candidate.get(key)
    return None


def _cell(value: Any) -> str:
    text = str(value if value is not None and value != "" else "unknown")
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _bool(value: Any) -> str:
    return str(bool(value)).lower()


def _num(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _delta(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "unknown"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{_num(value)}"
