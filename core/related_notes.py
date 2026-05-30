"""Phase 12.13c - Phantom Limb related notes (explain-only).

The safe first version of "pull related notes closer": given small note-like
records (lessons, proposal summaries, memory notes), explain which ones look
related to the current target/query/graph area and why. Notes that overlap the
query, target path, target node, current graph nodes, or come from a trusted
source (lesson/benchmark) are *attracted*; empty, unknown-source, generic, or
unrelated notes are *repelled*.

This module is **read-only / explain-only and deterministic**. It is NOT wired
into Phantom Limb ranking, CONTROL ranking, Evidence Spread scoring, patch
generation, validation, or benchmark scoring. It performs no model/API calls,
no subprocess, and no database access - it only inspects the records it is given.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Tunables (all local to this explain-only layer)
# --------------------------------------------------------------------------

# Attraction contributions.
_ATTRACT_QUERY = 0.40
_ATTRACT_TARGET_PATH = 0.35
_ATTRACT_TARGET_NODE = 0.30
_ATTRACT_USEFUL_SOURCE = 0.25
_ATTRACT_GRAPH_OVERLAP = 0.20

# Repulsion contributions.
_REPULSE_EMPTY = 0.35
_REPULSE_UNKNOWN_SOURCE = 0.25
_REPULSE_GENERIC = 0.20
_REPULSE_NO_OVERLAP = 0.20

# A note must clear this net score to be worth surfacing.
_SURFACE_THRESHOLD = 0.20

_USEFUL_SOURCES = {"lesson", "benchmark"}

# Titles that signal a catch-all / low-signal note.
_GENERIC_TITLES = ("misc", "todo", "general", "notes")
_GENERIC_TITLE_RE = re.compile(
    r"\b(" + "|".join(re.escape(g) for g in _GENERIC_TITLES) + r")\b",
    re.IGNORECASE,
)

RELATED_NOTES_GUARDRAIL = (
    "Related note attraction is explain-only. It does not change Phantom Limb "
    "ranking, CONTROL ranking, Evidence Spread scoring, patch generation, "
    "validation, or benchmark scoring."
)


@dataclass(frozen=True)
class RelatedNoteAttraction:
    note_id: str
    title: str
    source_type: str
    attraction: float
    repulsion: float
    net_score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
    should_surface: bool = False


# --------------------------------------------------------------------------
# Helpers (pure)
# --------------------------------------------------------------------------

def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_as_text(v) for v in value)
    return str(value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _contains(haystack: str, needle: str) -> bool:
    needle = (needle or "").strip().lower()
    if not needle:
        return False
    return needle in haystack


def _basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").split("/")[-1]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def classify_related_note_attraction(
    note,
    *,
    query: str = "",
    target_node: str = "",
    target_path: str = "",
    graph_nodes=None,
) -> RelatedNoteAttraction:
    """Explain why one note is attracted toward or repelled from attention.

    ``note`` is a small dict-like record (``note_id``, ``title``, ``source_type``,
    optional ``path``/``topic``/``tags`` and ``text``/``summary``/``confidence``).
    The result is read-only and deterministic.
    """
    note = note if isinstance(note, Mapping) else {}
    note_id = _as_text(note.get("note_id")).strip() or "unknown"
    title = _as_text(note.get("title")).strip()
    source_type = (_as_text(note.get("source_type")).strip().lower() or "unknown")

    text = " ".join(
        part
        for part in (_as_text(note.get("text")), _as_text(note.get("summary")))
        if part
    )
    tags = _as_text(note.get("tags"))
    path = " ".join(
        part
        for part in (_as_text(note.get("path")), _as_text(note.get("topic")))
        if part
    )

    # Field-scoped haystacks per the scoring spec.
    query_hay = " ".join((title, text, tags)).lower()
    path_hay = " ".join((path, text)).lower()
    node_hay = " ".join((text, title)).lower()
    graph_hay = " ".join((title, text, path, tags)).lower()

    reasons: list[str] = []

    # ---- Attraction ----------------------------------------------------
    attraction = 0.0
    query_match = _contains(query_hay, query)
    if query_match:
        attraction += _ATTRACT_QUERY
        reasons.append(f"query text appears in note (+{_ATTRACT_QUERY:.2f})")

    path_match = _contains(path_hay, target_path)
    if path_match:
        attraction += _ATTRACT_TARGET_PATH
        reasons.append(f"target path appears in note (+{_ATTRACT_TARGET_PATH:.2f})")

    node_match = _contains(node_hay, target_node)
    if node_match:
        attraction += _ATTRACT_TARGET_NODE
        reasons.append(f"target node appears in note (+{_ATTRACT_TARGET_NODE:.2f})")

    if source_type in _USEFUL_SOURCES:
        attraction += _ATTRACT_USEFUL_SOURCE
        reasons.append(f"useful source type ({source_type}) (+{_ATTRACT_USEFUL_SOURCE:.2f})")

    graph_match = False
    for gnode in graph_nodes or []:
        gtext = _as_text(gnode).strip()
        if not gtext:
            continue
        if _contains(graph_hay, gtext) or _contains(graph_hay, _basename(gtext)):
            graph_match = True
            break
    if graph_match:
        attraction += _ATTRACT_GRAPH_OVERLAP
        reasons.append(f"overlaps a current graph node (+{_ATTRACT_GRAPH_OVERLAP:.2f})")

    # ---- Repulsion -----------------------------------------------------
    repulsion = 0.0
    has_useful_text = bool((title + text + tags + path).strip())
    if not has_useful_text:
        repulsion += _REPULSE_EMPTY
        reasons.append(f"note is empty or missing useful text (-{_REPULSE_EMPTY:.2f})")

    if source_type == "unknown":
        repulsion += _REPULSE_UNKNOWN_SOURCE
        reasons.append(f"unknown source type (-{_REPULSE_UNKNOWN_SOURCE:.2f})")

    if title and _GENERIC_TITLE_RE.search(title):
        repulsion += _REPULSE_GENERIC
        reasons.append(f"generic note title (-{_REPULSE_GENERIC:.2f})")

    overlap = query_match or path_match or node_match or graph_match
    if not overlap:
        repulsion += _REPULSE_NO_OVERLAP
        reasons.append(f"no query/path/target overlap (-{_REPULSE_NO_OVERLAP:.2f})")

    net_score = _clamp(attraction - repulsion, -1.0, 1.0)
    should_surface = net_score > _SURFACE_THRESHOLD

    return RelatedNoteAttraction(
        note_id=note_id,
        title=title,
        source_type=source_type,
        attraction=round(attraction, 6),
        repulsion=round(repulsion, 6),
        net_score=round(net_score, 6),
        reasons=tuple(reasons),
        should_surface=should_surface,
    )


def explain_related_notes(
    notes,
    *,
    query: str = "",
    target_node: str = "",
    target_path: str = "",
    graph_nodes=None,
    limit: int = 5,
) -> list[RelatedNoteAttraction]:
    """Classify a batch of notes and return the strongest, net-score descending.

    Deterministic: ties keep their original relative order (stable sort). ``limit``
    caps how many are returned; a non-positive limit returns an empty list.
    """
    classified = [
        classify_related_note_attraction(
            note,
            query=query,
            target_node=target_node,
            target_path=target_path,
            graph_nodes=graph_nodes,
        )
        for note in (notes or [])
    ]
    classified.sort(key=lambda item: item.net_score, reverse=True)
    if limit is None:
        return classified
    if limit <= 0:
        return []
    return classified[:limit]


def format_related_notes_markdown(items) -> str:
    """Render related-note attraction explanations as a read-only Markdown table."""
    lines: list[str] = []
    lines.append("# Phantom Limb Related Notes (explain-only)")
    lines.append("")
    lines.append(
        "| note_id | title | source_type | attraction | repulsion | "
        "net_score | should_surface | reasons |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    items = list(items or [])
    if not items:
        lines.append("| _(no notes)_ | - | - | - | - | - | - | - |")
    else:
        for item in items:
            reasons = "; ".join(item.reasons) if item.reasons else "-"
            lines.append(
                "| {nid} | {title} | {src} | {a:.2f} | {r:.2f} | {n:+.2f} | {surface} | {rs} |".format(
                    nid=_md_cell(item.note_id),
                    title=_md_cell(item.title) or "_(untitled)_",
                    src=_md_cell(item.source_type),
                    a=item.attraction,
                    r=item.repulsion,
                    n=item.net_score,
                    surface="yes" if item.should_surface else "no",
                    rs=_md_cell(reasons),
                )
            )
    lines.append("")
    lines.append(f"> {RELATED_NOTES_GUARDRAIL}")
    lines.append("")
    return "\n".join(lines)


def _md_cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()
