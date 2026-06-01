"""Phase 13.9 - Memory Temperature tie-breaker retrieval (default off).

This is the first *behavior* hook for Memory Temperature, but it is disabled by
default and intentionally conservative when enabled. It accepts an
already-ordered list of lesson candidates (the final retrieval ordering) and may
only nudge their order *within near-equal relevance groups* using each lesson's
thermal band. It never:

  * overrides a clearly higher relevance score with a weak hot/cold signal,
  * hard-filters cold lessons,
  * revives or surfaces frozen / audit-only / blocked lessons,
  * mutates the input candidates, or
  * touches the original retrieval score.

The enable / tie-break flags are passed in as plain parameters
(``enabled`` / ``tiebreak_only``); this module reads no environment variables,
loads no lessons, and writes no storage — the enable decision is made by the
caller. As of Phase 13.11a this helper is wired into the live lesson-retrieval
ordering boundary (``core.lesson_retrieval.find_active_lessons``) behind a
default-off config flag read by that caller, so default live behavior and the
CONTROL prompt are unchanged; ``control_engine`` itself does not import it. It
performs no model/API calls, no DB writes, no
patch generation, no validation / benchmark execution, and no subprocess /
Docker lifecycle behavior.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.memory_temperature import classify_memory_temperature


MEMORY_TEMPERATURE_TIEBREAK_GUARDRAIL = (
    "Memory Temperature tie-breaker is default-off and conservative. When "
    "enabled it may only reorder lessons within near-equal relevance groups; it "
    "never overrides a clearly higher relevance score, never hard-filters cold "
    "lessons, and never revives frozen / audit-only / blocked lessons. It "
    "preserves the original retrieval score and does not change lesson loading, "
    "storage, promotion, blocking, CONTROL prompt format, model/API calls, DB "
    "writes, patching, validation, benchmark scoring, or subprocess behavior."
)

#: Key under which the tie-break adjustment metadata is attached to a copied
#: candidate. The original retrieval score and all other fields are preserved.
TIEBREAK_METADATA_KEY = "memory_temperature_tiebreak"

_DEFAULT_EPSILON = 0.02

# Lower rank == higher priority. Frozen records sink to the bottom of their
# group so temperature can never revive or surface them.
_BAND_RANK = {"hot": 0, "warm": 1, "cold": 2, "frozen": 3}


def apply_memory_temperature_tiebreaker(
    candidates,
    enabled: bool = False,
    tiebreak_only: bool = True,
    now=None,
) -> list[dict[str, Any]]:
    """Return candidates re-ordered by the Memory Temperature tie-breaker.

    Default-off behavior (``enabled=False``) is an exact pass-through: the
    candidates are returned in their original order, no metadata is attached,
    and the inputs are not mutated.

    When ``enabled`` is true and ``tiebreak_only`` is true, candidates are split
    into near-equal relevance groups (see :func:`group_near_equal_candidates`)
    and only re-ordered *within* each group by thermal band. Returned candidates
    are shallow copies carrying a :data:`TIEBREAK_METADATA_KEY` annotation; the
    inputs are never mutated and the original score is preserved.

    Broader (non-tie-break) reordering is intentionally not implemented in this
    phase; ``tiebreak_only=False`` currently behaves identically to the
    conservative tie-break path so a weak signal can never override a clearly
    higher relevance score.
    """
    items = list(candidates or [])
    if not enabled:
        # Exact original order, no annotation, no mutation.
        return list(items)

    indexed = list(enumerate(items))  # (original_index, candidate)
    groups = _group_indexed(indexed, score_key="score", epsilon=_DEFAULT_EPSILON)

    reordered: list[tuple[int, Any]] = []
    for group in groups:
        reordered.extend(_reorder_group(group, now=now))

    out: list[dict[str, Any]] = []
    for adjusted_pos, (original_index, candidate) in enumerate(reordered):
        classification = classify_memory_temperature(candidate, now=now)
        out.append(
            annotate_temperature_adjustment(
                candidate,
                original_rank=original_index + 1,
                adjusted_rank=adjusted_pos + 1,
                classification=classification,
            )
        )
    return out


def group_near_equal_candidates(
    candidates,
    score_key: str = "score",
    epsilon: float = _DEFAULT_EPSILON,
) -> list[list[dict[str, Any]]]:
    """Split candidates into near-equal relevance groups, preserving order.

    A new group starts whenever a candidate's score drops more than ``epsilon``
    below the score that *anchors* the current group (the group's first, and
    therefore highest-ranked, member). Anchoring to the group head bounds the
    total spread within a group to ``epsilon`` so a clearly lower-scored
    candidate can never share a group with a clearly higher-scored one.
    """
    indexed = list(enumerate(list(candidates or [])))
    return [[candidate for _idx, candidate in group]
            for group in _group_indexed(indexed, score_key=score_key, epsilon=epsilon)]


def annotate_temperature_adjustment(
    candidate,
    original_rank: int,
    adjusted_rank: int,
    classification,
) -> dict[str, Any]:
    """Return a shallow copy of ``candidate`` with tie-break metadata attached.

    The original retrieval score and every other field are preserved; only the
    :data:`TIEBREAK_METADATA_KEY` key is added (on the copy, never the input).
    """
    band = getattr(classification, "band", "")
    temperature = getattr(classification, "temperature", 0.0)
    tie_break_applied = original_rank != adjusted_rank

    out = dict(candidate) if isinstance(candidate, Mapping) else {"value": candidate}
    out[TIEBREAK_METADATA_KEY] = {
        "original_rank": original_rank,
        "adjusted_rank": adjusted_rank,
        "temperature_band": band,
        "temperature_score": temperature,
        "tie_break_applied": tie_break_applied,
        "reason": _adjustment_reason(band, original_rank, adjusted_rank),
    }
    return out


# --- internals -------------------------------------------------------------


def _group_indexed(indexed, score_key: str, epsilon: float):
    eps = _coerce_epsilon(epsilon)
    groups: list[list[tuple[int, Any]]] = []
    current: list[tuple[int, Any]] = []
    anchor_score = 0.0
    for original_index, candidate in indexed:
        score = _score_of(candidate, score_key)
        if not current:
            current = [(original_index, candidate)]
            anchor_score = score
            continue
        if abs(anchor_score - score) <= eps:
            current.append((original_index, candidate))
        else:
            groups.append(current)
            current = [(original_index, candidate)]
            anchor_score = score
    if current:
        groups.append(current)
    return groups


def _reorder_group(group, now):
    """Stable-sort one near-equal group by thermal band.

    The sort key keeps the group's original order for equal bands/temperatures
    so the only movement is band-driven: hot/warm rise, cold falls, frozen
    sinks last. Because the whole group is near-equal in relevance, this never
    overrides a clearly higher score, and because positions stay within the
    group's original span no candidate leaves its near-equal neighborhood.
    """
    decorated = []
    for within_index, (original_index, candidate) in enumerate(group):
        classification = classify_memory_temperature(candidate, now=now)
        band_rank = _BAND_RANK.get(classification.band, 9)
        decorated.append(
            (band_rank, -float(classification.temperature), within_index, original_index, candidate)
        )
    decorated.sort(key=lambda row: (row[0], row[1], row[2]))
    return [(original_index, candidate) for _b, _t, _w, original_index, candidate in decorated]


def _adjustment_reason(band: str, original_rank: int, adjusted_rank: int) -> str:
    band_label = band or "unknown"
    if adjusted_rank < original_rank:
        return (
            f"temperature band '{band_label}' raised rank "
            f"{original_rank}->{adjusted_rank} within near-equal tie-break group"
        )
    if adjusted_rank > original_rank:
        return (
            f"temperature band '{band_label}' lowered rank "
            f"{original_rank}->{adjusted_rank} within near-equal tie-break group"
        )
    return f"rank {original_rank} preserved; band '{band_label}'"


def _score_of(candidate, score_key: str) -> float:
    if isinstance(candidate, Mapping):
        return _coerce_float(candidate.get(score_key))
    return 0.0


def _coerce_epsilon(value) -> float:
    eps = _coerce_float(value)
    return eps if eps >= 0.0 else 0.0


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
