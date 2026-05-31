"""Phase 12.14a - Exponential Memory Temperature (explain-only).

Deterministic, physics-inspired cooling for already-loaded lesson/proposal/note
records. This module is pure: it does not load lessons, write storage, call
models/APIs, touch databases, inject prompts, or alter retrieval/ranking.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone


MEMORY_TEMPERATURE_GUARDRAIL = (
    "Memory temperature is explain-only. It does not change lesson retrieval, "
    "CONTROL prompts, ranking, patch generation, validation, benchmark scoring, "
    "or storage behavior."
)

_DEFAULT_BASE_TEMPERATURE = 0.80
_TRUSTED_BASE_TEMPERATURE = 0.85
_DEFAULT_COOLING_RATE = 0.03
_SURFACE_THRESHOLD = 0.40

_HUMAN_APPROVED_BOOST = 0.25
_REPEATED_USE_BOOST_PER_USE = 0.05
_REPEATED_USE_BOOST_CAP = 0.25
_RECENT_SUCCESS_BOOST = 0.10

_NEEDS_REVIEW_PENALTY = 0.10
_RISK_SCORE_PENALTY_CAP = 0.35

_HARD_FREEZE_STATUSES = {"blocked", "unsafe", "failed", "audit-only", "audit_only"}
_EXPLICIT_FROZEN_STATUSES = {"archive", "archived", "frozen"}


@dataclass(frozen=True)
class MemoryTemperature:
    item_id: str
    temperature: float
    band: str
    age_days: float
    cooling_rate: float
    base_temperature: float
    reheating_boost: float
    risk_penalty: float
    should_surface: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


def classify_memory_temperature(record, now=None) -> MemoryTemperature:
    """Classify one already-loaded memory-style record.

    Formula:
    ``T_now = clamp(T_base * exp(-cooling_rate * age_days) + reheating_boosts
    - risk_penalties, 0.0, 1.0)``.

    Hard-freeze records (blocked, unsafe, failed validation, audit-only) always
    return temperature 0.0, regardless of reheating.
    """
    if isinstance(record, MemoryTemperature):
        return record

    data = record if isinstance(record, Mapping) else {}
    now_dt, now_warning = _coerce_now(now)
    reasons: list[str] = []
    warnings: list[str] = []
    if now_warning:
        warnings.append(now_warning)
    if not isinstance(record, Mapping):
        warnings.append("record is not a dict-like mapping")

    item_id = _item_id(data)
    cooling_rate = _coerce_float(data.get("cooling_rate"), _DEFAULT_COOLING_RATE)
    if cooling_rate < 0:
        warnings.append("cooling_rate was negative; clamped to 0.0")
        cooling_rate = 0.0

    base_temperature = _base_temperature(data, reasons, warnings)
    timestamp, timestamp_warning = _record_timestamp(data)
    if timestamp_warning:
        warnings.append(timestamp_warning)
    age_days = 0.0
    if timestamp is not None:
        age_days = max(0.0, (now_dt - timestamp).total_seconds() / 86400.0)
        reasons.append(f"age_days={age_days:.2f}")
    else:
        reasons.append("missing timestamp; age_days defaults to 0.00")

    reheating_boost = _reheating_boost(data, reasons)
    risk_penalty = _risk_penalty(data, reasons, warnings)

    frozen_reason = _hard_freeze_reason(data)
    explicit_archive = _is_explicit_archive_or_frozen(data)
    if frozen_reason:
        temperature = 0.0
        band = "frozen"
        should_surface = False
        reasons.append(f"hard freeze: {frozen_reason}")
    else:
        raw = (
            base_temperature * math.exp(-cooling_rate * age_days)
            + reheating_boost
            - risk_penalty
        )
        temperature = _clamp(raw, 0.0, 1.0)
        if temperature >= 0.75:
            band = "hot"
        elif temperature >= 0.40:
            band = "warm"
        elif explicit_archive and temperature < 0.10:
            band = "frozen"
        else:
            # Per 12.14a, sub-0.10 valid records are still cold unless the
            # record is explicitly configured as archive/frozen.
            band = "cold"
        should_surface = band in {"hot", "warm"} and temperature >= _SURFACE_THRESHOLD

    return MemoryTemperature(
        item_id=item_id,
        temperature=round(temperature, 6),
        band=band,
        age_days=round(age_days, 6),
        cooling_rate=round(cooling_rate, 6),
        base_temperature=round(base_temperature, 6),
        reheating_boost=round(reheating_boost, 6),
        risk_penalty=round(risk_penalty, 6),
        should_surface=should_surface,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )


def classify_memory_batch(records, now=None, limit=None) -> list[MemoryTemperature]:
    """Classify records and sort hot/warm/cold before frozen, strongest first."""
    items = [classify_memory_temperature(record, now=now) for record in (records or [])]
    band_rank = {"hot": 0, "warm": 1, "cold": 2, "frozen": 3}
    items.sort(
        key=lambda item: (
            band_rank.get(item.band, 9),
            -item.temperature,
            item.item_id,
        )
    )
    if limit is None:
        return items
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        limit_int = 0
    if limit_int <= 0:
        return []
    return items[:limit_int]


def format_memory_temperature_markdown(results) -> str:
    """Render memory temperature explanations grouped by thermal band."""
    items = list(results or [])
    by_band = {band: [] for band in ("hot", "warm", "cold", "frozen")}
    for item in items:
        if not isinstance(item, MemoryTemperature):
            item = classify_memory_temperature(item)
        by_band.setdefault(item.band, []).append(item)

    lines: list[str] = []
    lines.append("# Memory Temperature (explain-only)")
    lines.append("")
    for band, title in (
        ("hot", "Hot"),
        ("warm", "Warm"),
        ("cold", "Cold"),
        ("frozen", "Frozen"),
    ):
        lines.append(f"## {title}")
        lines.append("")
        lines.append(
            "| item_id | temperature | age_days | cooling_rate | base_temperature | "
            "reheating_boost | risk_penalty | should_surface | reasons | warnings |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        band_items = by_band.get(band) or []
        if not band_items:
            lines.append("| _(none)_ | - | - | - | - | - | - | - | - | - |")
        else:
            for item in band_items:
                reasons = "; ".join(item.reasons) if item.reasons else "-"
                warnings = "; ".join(item.warnings) if item.warnings else "-"
                lines.append(
                    "| {item_id} | {temp:.2f} | {age:.2f} | {rate:.3f} | "
                    "{base:.2f} | {boost:.2f} | {penalty:.2f} | {surface} | "
                    "{reasons} | {warnings} |".format(
                        item_id=_md_cell(item.item_id),
                        temp=item.temperature,
                        age=item.age_days,
                        rate=item.cooling_rate,
                        base=item.base_temperature,
                        boost=item.reheating_boost,
                        penalty=item.risk_penalty,
                        surface="yes" if item.should_surface else "no",
                        reasons=_md_cell(reasons),
                        warnings=_md_cell(warnings),
                    )
                )
        lines.append("")
    lines.append(f"> {MEMORY_TEMPERATURE_GUARDRAIL}")
    lines.append("")
    return "\n".join(lines)


def _item_id(data: Mapping) -> str:
    for key in ("item_id", "id", "lesson_id", "proposal_id", "note_id"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "unknown"


def _coerce_now(value) -> tuple[datetime, str | None]:
    if value is None:
        return datetime.now(timezone.utc), None
    parsed = _parse_datetime(value)
    if parsed is None:
        return datetime.now(timezone.utc), "now could not be parsed; current UTC time used"
    return parsed, None


def _record_timestamp(data: Mapping) -> tuple[datetime | None, str | None]:
    for key in (
        "last_used_at",
        "last_seen_at",
        "updated_at",
        "created_at",
        "timestamp",
        "date",
    ):
        if key not in data:
            continue
        parsed = _parse_datetime(data.get(key))
        if parsed is not None:
            return parsed, None
        return None, f"{key} timestamp could not be parsed"
    return None, "missing timestamp"


def _parse_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _base_temperature(data: Mapping, reasons: list[str], warnings: list[str]) -> float:
    explicit = data.get("base_temperature")
    if explicit is not None:
        value = _coerce_float(explicit, _DEFAULT_BASE_TEMPERATURE)
        value = _clamp(value, 0.0, 1.0)
        reasons.append(f"explicit base_temperature={value:.2f}")
        return value

    if _truthy(data.get("trusted")) or str(data.get("source_type") or "").lower() in {
        "lesson",
        "benchmark",
    }:
        reasons.append("trusted/useful source base temperature")
        return _TRUSTED_BASE_TEMPERATURE

    if explicit is not None:
        warnings.append("base_temperature could not be parsed; default used")
    reasons.append("default base temperature")
    return _DEFAULT_BASE_TEMPERATURE


def _reheating_boost(data: Mapping, reasons: list[str]) -> float:
    boost = 0.0
    if _truthy(data.get("human_approved")) or _truthy(data.get("approved_by_human")):
        boost += _HUMAN_APPROVED_BOOST
        reasons.append(f"human-approved reheating +{_HUMAN_APPROVED_BOOST:.2f}")

    use_count = max(0, _coerce_int(_first_present(data, ("use_count", "uses", "retrieval_count"))))
    if use_count:
        use_boost = min(_REPEATED_USE_BOOST_CAP, use_count * _REPEATED_USE_BOOST_PER_USE)
        boost += use_boost
        reasons.append(f"repeated-use reheating +{use_boost:.2f}")

    if _truthy(data.get("recent_success")):
        boost += _RECENT_SUCCESS_BOOST
        reasons.append(f"recent-success reheating +{_RECENT_SUCCESS_BOOST:.2f}")

    explicit = data.get("reheating_boost")
    if explicit is not None:
        explicit_boost = max(0.0, _coerce_float(explicit, 0.0))
        boost += explicit_boost
        reasons.append(f"explicit reheating_boost +{explicit_boost:.2f}")

    return _clamp(boost, 0.0, 1.0)


def _risk_penalty(data: Mapping, reasons: list[str], warnings: list[str]) -> float:
    penalty = 0.0
    if _truthy(data.get("needs_human_review")):
        penalty += _NEEDS_REVIEW_PENALTY
        reasons.append(f"needs-review risk penalty -{_NEEDS_REVIEW_PENALTY:.2f}")

    explicit = data.get("risk_penalty")
    if explicit is not None:
        explicit_penalty = max(0.0, _coerce_float(explicit, 0.0))
        penalty += explicit_penalty
        reasons.append(f"explicit risk_penalty -{explicit_penalty:.2f}")

    risk_score = data.get("risk_score")
    if risk_score is not None:
        risk_value = _coerce_float(risk_score, 0.0)
        if risk_value < 0:
            warnings.append("risk_score was negative; ignored")
            risk_value = 0.0
        score_penalty = min(_RISK_SCORE_PENALTY_CAP, risk_value)
        penalty += score_penalty
        reasons.append(f"risk_score penalty -{score_penalty:.2f}")

    return _clamp(penalty, 0.0, 1.0)


def _hard_freeze_reason(data: Mapping) -> str:
    status = str(data.get("status") or data.get("promotion") or "").strip().lower()
    if status in _HARD_FREEZE_STATUSES:
        return status.replace("_", "-")
    if _truthy(data.get("blocked")):
        return "blocked"
    if _truthy(data.get("unsafe")) or _truthy(data.get("is_unsafe")):
        return "unsafe"
    if _truthy(data.get("audit_only")) or _truthy(data.get("audit-only")):
        return "audit-only"
    if _truthy(data.get("failed_validation")):
        return "failed validation"
    validation = data.get("validation_ok")
    if validation is False:
        return "failed validation"
    validation_status = str(data.get("validation_status") or "").strip().lower()
    if validation_status in {"failed", "fail", "error", "invalid"}:
        return "failed validation"
    return ""


def _is_explicit_archive_or_frozen(data: Mapping) -> bool:
    status = str(data.get("status") or "").strip().lower()
    if status in _EXPLICIT_FROZEN_STATUSES:
        return True
    return _truthy(data.get("archive")) or _truthy(data.get("frozen"))


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _first_present(data: Mapping, keys: tuple[str, ...]):
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value, default: int = 0) -> int:
    try:
        if value is None or isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _md_cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()
