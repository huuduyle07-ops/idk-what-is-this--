"""Deterministic duplicate-hint detection for lesson records.

No model calls. Takes an already-loaded list[dict] and returns groups of
likely-duplicate lessons based on pure-Python signals.

Phase 11.3 adds anti-lesson-aware signals. ``find_duplicate_groups`` gains an
extra reason class when *both* records are anti-lessons (same
tempting_wrong_pattern / why_wrong / overlapping evidence_refs /
related_lesson_ids), and a per-candidate detector,
``detect_anti_lesson_duplicates``, returns a
``{duplicate_of, possible_duplicates, reasons}`` advisory. All of this is
ADVISORY only — it never blocks, merges, promotes, or mutates any record.
"""
from __future__ import annotations

import re
from collections import defaultdict

from core.lesson_store import is_anti_lesson


_TITLE_NORM_RE = re.compile(r"[^\w\s]")
_JACCARD_THRESHOLD = 0.5
_MIN_SHARED_TAGS = 2


def _normalize_title(title: str) -> str:
    # Remove punctuation/special chars, lowercase, collapse multiple spaces
    normalized = _TITLE_NORM_RE.sub("", title.lower()).strip()
    # Collapse multiple spaces into single space
    normalized = " ".join(normalized.split())
    return normalized


def _normalize_text(value) -> str:
    """Normalize an arbitrary text field the same way as titles (lenient)."""
    if not isinstance(value, str):
        return ""
    return _normalize_title(value)


def _anti_candidate(record: dict) -> dict:
    cand = record.get("candidate") if isinstance(record, dict) else None
    return cand if isinstance(cand, dict) else {}


def _ref_set(raw) -> set[str]:
    """Normalize an evidence_refs list to a comparable set (separator/case)."""
    if not isinstance(raw, list):
        return set()
    out: set[str] = set()
    for ref in raw:
        if isinstance(ref, str) and ref.strip():
            out.add(ref.replace("\\", "/").strip().lower())
    return out


def _id_set(raw) -> set[str]:
    if not isinstance(raw, list):
        return set()
    return {item.strip() for item in raw if isinstance(item, str) and item.strip()}


def _anti_lesson_overlap_reasons(a: dict, b: dict) -> list[str]:
    """Deterministic anti-lesson duplicate signals between two records.

    Pure and cheap (string normalization + set overlap; no embeddings, no model
    calls). Returns hint strings; an empty list means "no overlap".
    """
    reasons: list[str] = []
    ca, cb = _anti_candidate(a), _anti_candidate(b)

    ta, tb = _normalize_text(a.get("title")), _normalize_text(b.get("title"))
    if ta and ta == tb:
        reasons.append(f"same normalized title: {ta!r}")

    pa = _normalize_text(ca.get("tempting_wrong_pattern"))
    pb = _normalize_text(cb.get("tempting_wrong_pattern"))
    if pa and pa == pb:
        reasons.append("same tempting_wrong_pattern")

    wa = _normalize_text(ca.get("why_wrong"))
    wb = _normalize_text(cb.get("why_wrong"))
    if wa and wa == wb:
        reasons.append("same why_wrong")

    shared_evidence = _ref_set(ca.get("evidence_refs")) & _ref_set(cb.get("evidence_refs"))
    if shared_evidence:
        reasons.append(f"overlapping evidence_refs: {sorted(shared_evidence)}")

    shared_related = _id_set(ca.get("related_lesson_ids")) & _id_set(cb.get("related_lesson_ids"))
    if shared_related:
        reasons.append(f"overlapping related_lesson_ids: {sorted(shared_related)}")

    # Same specific provenance. The generic "manual" source is excluded so two
    # hand-written anti-lessons don't always look related.
    sr_a, sr_b = a.get("source_report"), b.get("source_report")
    if sr_a and sr_b and sr_a == sr_b:
        reasons.append(f"same source_report ({sr_a!r})")
    src_a = (a.get("source") or "").strip().lower()
    src_b = (b.get("source") or "").strip().lower()
    if src_a and src_a == src_b and src_a != "manual":
        reasons.append(f"same source ({src_a!r})")

    return reasons


def _is_strong_anti_duplicate(a: dict, b: dict) -> bool:
    """Strong (near-certain) anti-lesson duplicate signal.

    The defining trait of an anti-lesson is its ``tempting_wrong_pattern`` (the
    thing you must NOT do), so an identical pattern is decisive. Failing that, a
    matching title *and* matching why_wrong is treated as strong too.
    """
    ca, cb = _anti_candidate(a), _anti_candidate(b)
    pa = _normalize_text(ca.get("tempting_wrong_pattern"))
    pb = _normalize_text(cb.get("tempting_wrong_pattern"))
    if pa and pa == pb:
        return True
    ta, tb = _normalize_text(a.get("title")), _normalize_text(b.get("title"))
    wa = _normalize_text(ca.get("why_wrong"))
    wb = _normalize_text(cb.get("why_wrong"))
    return bool(ta and ta == tb and wa and wa == wb)


def detect_anti_lesson_duplicates(record: dict, existing: list[dict]) -> dict:
    """Advisory duplicate check for an anti-lesson ``record``.

    Compares ``record`` against ``existing`` records, considering only those
    whose kind is ``anti_lesson`` (a normal lesson is never reported as an
    anti-lesson duplicate). Records sharing ``record``'s id are skipped so a
    just-saved record can be passed straight through.

    Returns ``{duplicate_of, possible_duplicates, reasons}``:
      * ``duplicate_of`` — id of the first *strong* match (or None);
      * ``possible_duplicates`` — list of ``{lesson_id, reasons, strong}`` for
        every record sharing at least one signal;
      * ``reasons`` — de-duped union of all hint strings.

    Pure and advisory: never blocks, merges, promotes, or mutates anything.
    """
    self_id = record.get("id") if isinstance(record, dict) else None
    possible: list[dict] = []
    duplicate_of: str | None = None
    reasons: list[str] = []
    seen_reasons: set[str] = set()

    for other in existing or []:
        if not isinstance(other, dict) or not is_anti_lesson(other):
            continue
        oid = other.get("id")
        if not isinstance(oid, str) or not oid or oid == self_id:
            continue
        pair_reasons = _anti_lesson_overlap_reasons(record, other)
        if not pair_reasons:
            continue
        strong = _is_strong_anti_duplicate(record, other)
        possible.append({"lesson_id": oid, "reasons": pair_reasons, "strong": strong})
        if strong and duplicate_of is None:
            duplicate_of = oid
        for r in pair_reasons:
            if r not in seen_reasons:
                seen_reasons.add(r)
                reasons.append(r)

    return {
        "duplicate_of": duplicate_of,
        "possible_duplicates": possible,
        "reasons": reasons,
    }


def anti_lesson_overlap_reasons_for_group(lessons: list[dict]) -> list[str]:
    """De-duped union of pairwise anti-lesson overlap reasons across a group.

    Used to surface "why these overlap" in an anti+anti merge preview. Pure.
    """
    out: list[str] = []
    seen: set[str] = set()
    n = len(lessons)
    for i in range(n):
        for j in range(i + 1, n):
            for r in _anti_lesson_overlap_reasons(lessons[i], lessons[j]):
                if r not in seen:
                    seen.add(r)
                    out.append(r)
    return out


def _jaccard(a: str, b: str) -> float:
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _duplicate_hints(a: dict, b: dict) -> list[str]:
    """Return hint reason strings if a and b are likely duplicates, else []."""
    reasons: list[str] = []

    sr_a = a.get("source_report")
    sr_b = b.get("source_report")
    cn_a = a.get("case_name")
    cn_b = b.get("case_name")

    # Signal 1: same source_report + case_name
    if sr_a and sr_b and cn_a and cn_b and sr_a == sr_b and cn_a == cn_b:
        reasons.append(
            f"same source_report ({sr_a!r}) and case_name ({cn_a!r})"
        )

    # Signal 2: same normalized title
    t_a = _normalize_title(a.get("title") or "")
    t_b = _normalize_title(b.get("title") or "")
    if t_a and t_b and t_a == t_b:
        reasons.append(f"same normalized title: {t_a!r}")

    # Signal 3: same language + category + >=2 shared tags
    cand_a = a.get("candidate") or {}
    cand_b = b.get("candidate") or {}
    lang_a = (cand_a.get("language") or "").lower().strip()
    lang_b = (cand_b.get("language") or "").lower().strip()
    cat_a = (cand_a.get("category") or "").lower().strip()
    cat_b = (cand_b.get("category") or "").lower().strip()
    tags_a = set(a.get("tags") or [])
    tags_b = set(b.get("tags") or [])
    shared = tags_a & tags_b
    if (
        lang_a and lang_a == lang_b
        and cat_a and cat_a == cat_b
        and len(shared) >= _MIN_SHARED_TAGS
    ):
        reasons.append(
            f"same language ({lang_a!r}) + category ({cat_a!r}) "
            f"with {len(shared)} shared tags: {sorted(shared)}"
        )

    # Signal 4: summary token Jaccard >= threshold
    sum_a = a.get("summary") or ""
    sum_b = b.get("summary") or ""
    if sum_a and sum_b and _jaccard(sum_a, sum_b) >= _JACCARD_THRESHOLD:
        reasons.append(f"summary token Jaccard >= {_JACCARD_THRESHOLD}")

    # Signal 5: same case_name, different source_report (different runs)
    if cn_a and cn_b and cn_a == cn_b and sr_a and sr_b and sr_a != sr_b:
        reasons.append(
            f"same case_name ({cn_a!r}) from different runs"
        )

    # Phase 11.3: when BOTH records are anti-lessons, add anti-specific signals
    # (tempting_wrong_pattern / why_wrong / evidence_refs / related_lesson_ids).
    # Gated on both being anti so a normal lesson and an anti-lesson are never
    # grouped as duplicates. Reasons are de-duped against the generic ones above.
    if is_anti_lesson(a) and is_anti_lesson(b):
        for r in _anti_lesson_overlap_reasons(a, b):
            if r not in reasons:
                reasons.append(r)

    return reasons


def find_duplicate_groups(
    lessons: list[dict],
    *,
    min_group_size: int = 2,
) -> list[dict]:
    """Return groups of lessons sharing at least one duplicate hint signal.

    Each group: {"lesson_ids": [...], "hint_reasons": [...]}
    """
    n = len(lessons)
    parent = list(range(n))
    edge_reasons: dict[tuple[int, int], list[str]] = {}

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(x: int, y: int) -> None:
        rx, ry = _find(x), _find(y)
        if rx != ry:
            parent[ry] = rx

    for i in range(n):
        for j in range(i + 1, n):
            hints = _duplicate_hints(lessons[i], lessons[j])
            if hints:
                edge_reasons[(i, j)] = hints
                _union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[_find(i)].append(i)

    result = []
    for members in groups.values():
        if len(members) < min_group_size:
            continue
        seen: set[str] = set()
        all_reasons: list[str] = []
        for ai in members:
            for bi in members:
                if ai >= bi:
                    continue
                for r in edge_reasons.get((ai, bi), []):
                    if r not in seen:
                        seen.add(r)
                        all_reasons.append(r)
        ids = [lessons[k]["id"] for k in members if lessons[k].get("id")]
        result.append({"lesson_ids": ids, "hint_reasons": all_reasons})

    return result
