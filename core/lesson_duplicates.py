"""Deterministic duplicate-hint detection for lesson records.

No model calls. Takes an already-loaded list[dict] and returns groups of
likely-duplicate lessons based on five pure-Python signals.
"""
from __future__ import annotations

import re
from collections import defaultdict


_TITLE_NORM_RE = re.compile(r"[^\w\s]")
_JACCARD_THRESHOLD = 0.5
_MIN_SHARED_TAGS = 2


def _normalize_title(title: str) -> str:
    # Remove punctuation/special chars, lowercase, collapse multiple spaces
    normalized = _TITLE_NORM_RE.sub("", title.lower()).strip()
    # Collapse multiple spaces into single space
    normalized = " ".join(normalized.split())
    return normalized


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
