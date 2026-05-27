"""Phase 4.7e - local Dream research reference imports.

This module turns pasted external notes into local, report-only artifacts under
`.agent/dream_references/<reference_id>/`. It only normalizes user-supplied
text; URLs remain inert strings and imported claims are never treated as facts.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import get_agent_dir


REFERENCE_SOURCE_TYPES: frozenset[str] = frozenset({
    "manual_paste",
    "zapier_discord",
    "paper_notes",
    "web_summary",
    "other",
})

SOURCE_ENTRY_TYPES: frozenset[str] = frozenset({
    "paper",
    "docs",
    "blog",
    "forum",
    "unknown",
    # Phase 4.7e-a — added by the loose normalizer's source-type inference.
    # Backward compatible: existing callers pass `paper`/`docs`/`blog`/`forum`
    # / `unknown` and continue to work.
    "official_docs",
    "book",
    "web_guide",
})

SOURCE_RELIABILITY: frozenset[str] = frozenset({
    "high",
    "medium",
    "low",
    "unknown",
})

ALLOWED_REFERENCE_FILES: frozenset[str] = frozenset({
    "reference.md",
    "reference.json",
})

REFERENCE_ID_RE = re.compile(r"^\d{8}-\d{6}-[a-z0-9][a-z0-9-]{0,80}(?:-\d+)?$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# ---------------------------------------------------------------------------
# Phase 4.7e-a — Loose Research Note Normalizer
# ---------------------------------------------------------------------------
#
# Maps Zapier / Discord style headings to canonical section keys. The lookup
# is case-insensitive and tolerant of markdown heading markers and a trailing
# colon. Heading keys with value `None` mean "section recognized but skip its
# content" (e.g. the "Research Results" preamble label).

_LOOSE_HEADINGS: dict[str, str | None] = {
    "research results": None,
    "summary": "summary",
    "key papers": "sources_papers",
    "key papers & articles": "sources_papers",
    "key papers and articles": "sources_papers",
    "papers": "sources_papers",
    "references": "sources_papers",
    "key insights": "key_ideas",
    "insights": "key_ideas",
    "resources": "sources_links",
    "resources & links": "sources_links",
    "resources and links": "sources_links",
    "links": "sources_links",
    "sources": "sources_links",
    "risks": "risks_or_weaknesses",
    "weaknesses": "risks_or_weaknesses",
    "risks / weaknesses": "risks_or_weaknesses",
    "risks/weaknesses": "risks_or_weaknesses",
    "risks and weaknesses": "risks_or_weaknesses",
    "what c.a.t.t.u.s should not assume": "do_not_assume",
    "what cattus should not assume": "do_not_assume",
    "do not assume": "do_not_assume",
    "what not to assume": "do_not_assume",
    "suggested dream trial input": "suggested_dream_trial_input",
    "suggested trial input": "suggested_dream_trial_input",
    "trial input": "suggested_dream_trial_input",
}

_LOOSE_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_LOOSE_BULLET_PREFIX_RE = re.compile(r"^(?:\d+[.):]\s*|[-*+]\s*)")
_LOOSE_MD_HEADING_PREFIX_RE = re.compile(r"^#+\s*")

# Sentinel return values for `_loose_classify_line()`. Using object identity
# keeps the distinction unambiguous when a heading also maps to `None`
# (the skip-section case).
_LOOSE_NOT_A_HEADING = object()
_LOOSE_SKIP_SECTION = object()

# Conservative defaults appended when a loose research block omits the
# matching section entirely. Phase 4.7e-a requires the warnings be present
# so downstream readers can't mistake silence for "no risks identified".
_LOOSE_DEFAULT_RISKS: tuple[str, ...] = (
    "Imported research was not independently verified.",
    "Source labels may be inaccurate.",
    "Performance or quality claims need supporting evidence.",
)

_LOOSE_DEFAULT_DO_NOT_ASSUME: tuple[str, ...] = (
    "Do not treat imported research as verified truth.",
    "Do not auto-create patches or proposals from this reference alone.",
)


@dataclass
class DreamReferenceResult:
    reference_id: str
    reference_dir: str
    json_path: str
    markdown_path: str
    summary: str


def references_root(repo_path: str) -> Path:
    repo_root = _resolve_repo_path(repo_path)
    return get_agent_dir(str(repo_root)) / "dream_references"


def _resolve_repo_path(repo_path: str | Path) -> Path:
    path_text = str(repo_path or "").strip()
    if not path_text:
        raise ValueError("repo_path is required")
    repo_root = Path(path_text).expanduser().resolve()
    if not repo_root.is_dir():
        raise ValueError(f"repo_path is not a directory: {repo_path}")
    return repo_root


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text or "").strip("-").lower()
    return slug[:max_len] or "reference"


def _build_reference_id(now: datetime, topic: str) -> str:
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{_slugify(topic)}"


def _normalize_reference_source_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "manual_paste"
    if normalized in REFERENCE_SOURCE_TYPES:
        return normalized
    return "other"


def _normalize_source_entry_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in SOURCE_ENTRY_TYPES else "unknown"


def _normalize_reliability(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in SOURCE_RELIABILITY else "unknown"


def _clean_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    cleaned: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
    return cleaned


def _normalize_sources(sources) -> list[dict]:
    if sources is None:
        return []
    if isinstance(sources, dict):
        source_items = [sources]
    elif isinstance(sources, (list, tuple)):
        source_items = list(sources)
    else:
        source_items = [sources]

    normalized: list[dict] = []
    for item in source_items:
        if isinstance(item, dict):
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            source_type = _normalize_source_entry_type(item.get("source_type"))
            reliability = _normalize_reliability(item.get("reliability"))
            why = str(item.get("why_relevant") or "").strip()
        else:
            title = str(item or "").strip()
            url = ""
            source_type = "unknown"
            reliability = "unknown"
            why = ""

        if not any([title, url, why]) and source_type == "unknown" and reliability == "unknown":
            continue
        normalized.append({
            "title": title,
            "url": url,
            "source_type": source_type,
            "reliability": reliability,
            "why_relevant": why,
        })
    return normalized


def _has_structured_fields(
    sources: list[dict],
    key_ideas: list[str],
    risks_or_weaknesses: list[str],
    do_not_assume: list[str],
    suggested_dream_trial_input: str,
) -> bool:
    return bool(
        sources
        or key_ideas
        or risks_or_weaknesses
        or do_not_assume
        or suggested_dream_trial_input.strip()
    )


def _first_snippet(text: str, max_chars: int = 360) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    candidates: list[str] = []
    for line in stripped.splitlines():
        line = line.strip().lstrip("-*# ").strip()
        if line:
            candidates.append(line)
    if not candidates:
        candidates = [part.strip() for part in _SENTENCE_SPLIT_RE.split(stripped) if part.strip()]
    snippet = candidates[0] if candidates else stripped
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rstrip() + "..."
    return snippet


def _build_summary(raw_input: str, key_ideas: list[str], sources: list[dict]) -> str:
    snippet = _first_snippet(raw_input)
    if snippet:
        return f"Imported notes claim: {snippet}"
    if key_ideas:
        return f"Imported structured notes claim: {key_ideas[0]}"
    if sources:
        title = sources[0].get("title") or "an imported source"
        return f"Imported source metadata reports: {title}"
    return "Imported notes contain structured fields only."


def _list_section(values: list[str]) -> list[str]:
    if not values:
        return ["- _None recorded._"]
    return [f"- {value}" for value in values]


def _render_reference_markdown(payload: dict) -> str:
    lines: list[str] = [
        "# Dream Research Reference",
        "",
        "## Topic",
        "",
        payload["topic"],
        "",
        "## Source Type",
        "",
        payload["source_type"],
        "",
        "## Summary",
        "",
        payload["summary"],
        "",
        "## Sources",
    ]

    sources = payload.get("sources") or []
    if not sources:
        lines.append("- _No sources listed._")
    for source in sources:
        title = source.get("title") or "_Untitled source_"
        # Phase 4.7e-b: render an empty URL as `_missing_` so the reader can
        # tell a title-only entry apart from a fully-specified source at a
        # glance instead of seeing a dangling `URL:` line.
        url_text = source.get("url") or "_missing_"
        lines.extend([
            f"- {title}",
            f"  - URL: {url_text}",
            f"  - Type: {source.get('source_type') or 'unknown'}",
            f"  - Reliability: {source.get('reliability') or 'unknown'}",
            f"  - Why relevant: {source.get('why_relevant') or ''}",
        ])

    lines.extend([
        "",
        "## Key Ideas",
        "",
        *_list_section(payload.get("key_ideas") or []),
        "",
        "## Risks / Weaknesses",
        "",
        *_list_section(payload.get("risks_or_weaknesses") or []),
        "",
        "## What C.A.T.T.U.S Should Not Assume",
        "",
        *_list_section(payload.get("do_not_assume") or []),
        "",
        "## Suggested Dream Trial Input",
        "",
        payload.get("suggested_dream_trial_input") or "_None recorded._",
        "",
        "## Raw Input",
        "",
        payload.get("raw_input") or "_No raw input; structured fields only._",
        "",
    ])
    return "\n".join(lines)


def _allocate_reference_dir(root: Path, reference_id: str) -> tuple[str, Path]:
    root_resolved = root.resolve()
    candidate_id = reference_id
    suffix = 0
    while True:
        candidate = (root / candidate_id).resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            raise ValueError("reference path escapes dream_references root")
        if not candidate.exists():
            return candidate_id, candidate
        suffix += 1
        candidate_id = f"{reference_id}-{suffix}"


# ---------------------------------------------------------------------------
# Loose normalizer (Phase 4.7e-a)
# ---------------------------------------------------------------------------

def _loose_classify_line(line: str):
    """Classify a raw line as a heading transition or content.

    Returns one of:
      - `_LOOSE_NOT_A_HEADING` — append line to the current section
      - `_LOOSE_SKIP_SECTION`  — heading recognized; subsequent lines drop
      - a section-key string   — heading recognized; subsequent lines belong
                                  to that section
    """
    raw = (line or "").strip()
    if not raw:
        return _LOOSE_NOT_A_HEADING
    md_stripped = _LOOSE_MD_HEADING_PREFIX_RE.sub("", raw)
    candidate = md_stripped.rstrip(":").strip().lower()
    if not candidate or candidate not in _LOOSE_HEADINGS:
        return _LOOSE_NOT_A_HEADING
    target = _LOOSE_HEADINGS[candidate]
    return _LOOSE_SKIP_SECTION if target is None else target


def _loose_split_into_sections(raw_input: str) -> dict[str, str]:
    """Walk the raw text line by line and bucket content into canonical
    sections. Anything before the first recognized heading is discarded so
    Zapier preamble like "Research Results" never leaks into the summary."""
    if not raw_input:
        return {}
    sections: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in raw_input.splitlines():
        result = _loose_classify_line(line)
        if result is _LOOSE_NOT_A_HEADING:
            if current_key:
                sections.setdefault(current_key, []).append(line)
            continue
        if result is _LOOSE_SKIP_SECTION:
            current_key = None
            continue
        current_key = result  # heading mapped to a real section key
    return {k: "\n".join(lines).strip() for k, lines in sections.items()}


_LOOSE_TITLE_ONLY_WARNING = "Title-only source from imported notes; URL missing."
_LOOSE_TITLE_MIN_LEN = 3
_LOOSE_SEPARATOR_RE = re.compile(r"[-=*_~\s]+")


def _loose_normalize_title_for_dedup(title: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation — for title dedup only."""
    s = (title or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s


def _loose_parse_source_line(line: str) -> dict | None:
    """Pull one source dict out of a single line.

    Phase 4.7e-b: a line with no URL but a real-looking title now becomes a
    title-only source dict ({"title": ..., "url": ""}) instead of being
    silently dropped. Noise lines — markdown headings, pure separators,
    generic section labels echoed in body, fragments under 3 chars — still
    return None.
    """
    raw = (line or "").strip()
    if not raw:
        return None

    # Strip a leading bullet / numeric prefix once.
    stripped = _LOOSE_BULLET_PREFIX_RE.sub("", raw).strip()
    if not stripped:
        return None

    # Markdown heading echoed in the body — skip.
    if stripped.startswith("#"):
        return None

    # Pure separator (---, ===, etc.) — nothing meaningful left after
    # stripping separator chars.
    if not _LOOSE_SEPARATOR_RE.sub("", stripped):
        return None

    # Fragments shorter than 3 characters can't carry a useful title.
    if len(stripped) < _LOOSE_TITLE_MIN_LEN:
        return None

    # Echoes of a recognized section heading inside the body — skip.
    label_check = stripped.rstrip(":").strip().lower()
    if label_check in _LOOSE_HEADINGS:
        return None

    urls = _LOOSE_URL_RE.findall(stripped)
    if urls:
        url = urls[0].rstrip(",.;)\"'")
        title = stripped.replace(urls[0], "").strip()
        title = re.sub(r"^[\-:\s]+", "", title)
        title = re.sub(r"[\-:\s]+$", "", title)
        return {"title": title, "url": url}

    # Title-only: clean leading/trailing punctuation but keep internal colons
    # (e.g. "grep: A Pattern Matching Utility").
    title = re.sub(r"^[\-:\s]+", "", stripped)
    title = re.sub(r"[\-:\s]+$", "", title)
    title = title.rstrip(".").strip()
    if len(title) < _LOOSE_TITLE_MIN_LEN:
        return None
    return {"title": title, "url": ""}


def _loose_infer_source_type(url: str) -> str:
    u = (url or "").lower()
    if "gnu.org/software" in u and ("/manual" in u or "/refman" in u):
        return "official_docs"
    if "/manual/" in u or u.endswith("/manual") or "/manual.html" in u:
        return "official_docs"
    if "/refman/" in u or u.endswith("/refman"):
        return "official_docs"
    if "/reference/" in u or u.endswith("/reference"):
        return "official_docs"
    if "/spec/" in u:
        return "official_docs"
    if "docs." in u or "/docs/" in u or u.endswith("/docs"):
        return "official_docs"
    if "oreilly.com" in u or "catb.org" in u or "/book/" in u or u.endswith(".epub"):
        return "book"
    if "regular-expressions.info" in u:
        return "web_guide"
    if "blog" in u or "/forum/" in u or "stackoverflow.com" in u or "reddit.com" in u:
        return "blog"
    return "unknown"


def _loose_infer_reliability(source_type: str) -> str:
    if source_type == "official_docs":
        return "high"
    if source_type == "book":
        return "medium"
    return "unknown"


def _loose_extract_sources(sections: dict[str, str]) -> list[dict]:
    """Pull deduplicated source dicts from the papers + links sections.

    Phase 4.7e-b: URL-based and title-only lines are both captured. URL
    sources are deduplicated by URL. Title-only sources are deduplicated
    among themselves by normalized title, and a title-only entry is
    suppressed when a URL source with the same normalized title already
    exists (the URL source is preferred).
    """
    blob = "\n".join(filter(None, [
        sections.get("sources_papers", ""),
        sections.get("sources_links", ""),
    ]))
    if not blob.strip():
        return []

    # Parse once, then segregate by URL-presence so we can run two passes
    # without re-parsing.
    parsed_url_lines: list[dict] = []
    parsed_title_only_lines: list[dict] = []
    for line in blob.splitlines():
        parsed = _loose_parse_source_line(line)
        if parsed is None:
            continue
        if parsed["url"]:
            parsed_url_lines.append(parsed)
        else:
            parsed_title_only_lines.append(parsed)

    seen_urls: set[str] = set()
    url_source_titles: set[str] = set()
    url_results: list[dict] = []
    for parsed in parsed_url_lines:
        url = parsed["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        source_type = _loose_infer_source_type(url)
        url_source_titles.add(_loose_normalize_title_for_dedup(parsed["title"]))
        url_results.append({
            "title": parsed["title"],
            "url": url,
            "source_type": source_type,
            "reliability": _loose_infer_reliability(source_type),
            "why_relevant": "",
        })

    seen_titles: set[str] = set()
    title_only_results: list[dict] = []
    for parsed in parsed_title_only_lines:
        norm = _loose_normalize_title_for_dedup(parsed["title"])
        if not norm:
            continue
        if norm in url_source_titles:
            # URL source preferred — drop the bare title to avoid a phantom
            # duplicate of the same idea.
            continue
        if norm in seen_titles:
            continue
        seen_titles.add(norm)
        title_only_results.append({
            "title": parsed["title"],
            "url": "",
            "source_type": "unknown",
            "reliability": "unknown",
            "why_relevant": _LOOSE_TITLE_ONLY_WARNING,
        })

    return url_results + title_only_results


def _loose_extract_bullets(text: str) -> list[str]:
    """Split a section blob into one entry per non-empty line, stripping
    bullet / numeric prefixes. Empty input → empty list."""
    if not text:
        return []
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = _LOOSE_BULLET_PREFIX_RE.sub("", stripped).strip()
        if cleaned:
            out.append(cleaned)
    return out


def normalize_loose_research_text(raw_input: str, topic: str | None = None) -> dict:
    """Parse Zapier / Discord-style research notes into a canonical dict.

    The returned dict carries:
      - raw_input: the input string, unchanged
      - summary: text under a Summary-like heading
      - sources: deduplicated list of {title, url, source_type, reliability,
        why_relevant} drawn from "Key Papers", "Resources", "Links", "Sources"
      - key_ideas: bullets under "Key Insights"
      - risks_or_weaknesses: bullets under "Risks / Weaknesses" (or
        conservative defaults if the section is absent)
      - do_not_assume: bullets under "What … Should Not Assume" (or
        conservative defaults if the section is absent)
      - suggested_dream_trial_input: text under "Suggested Dream Trial Input"

    No network I/O. No model API calls. The topic parameter is accepted for
    forward compatibility; the current implementation does not branch on it.
    """
    text = raw_input or ""
    sections = _loose_split_into_sections(text)

    summary = sections.get("summary", "").strip()
    sources = _loose_extract_sources(sections)
    key_ideas = _loose_extract_bullets(sections.get("key_ideas", ""))
    risks = _loose_extract_bullets(sections.get("risks_or_weaknesses", ""))
    do_not = _loose_extract_bullets(sections.get("do_not_assume", ""))
    suggested = sections.get("suggested_dream_trial_input", "").strip()

    if not risks:
        risks = list(_LOOSE_DEFAULT_RISKS)
    if not do_not:
        do_not = list(_LOOSE_DEFAULT_DO_NOT_ASSUME)

    # Phase 4.7e-a invariant: the original input string is preserved verbatim
    # so downstream consumers can re-parse if heuristics change.
    return {
        "raw_input": text,
        "topic": (topic or "").strip(),
        "summary": summary,
        "sources": sources,
        "key_ideas": key_ideas,
        "risks_or_weaknesses": risks,
        "do_not_assume": do_not,
        "suggested_dream_trial_input": suggested,
    }


def create_dream_reference(
    repo_path,
    topic,
    raw_input,
    source_type="manual_paste",
    sources=None,
    key_ideas=None,
    risks_or_weaknesses=None,
    do_not_assume=None,
    suggested_dream_trial_input="",
    normalize_loose=False,
    now=None,
) -> DreamReferenceResult:
    topic_text = str(topic or "").strip()
    if not topic_text:
        raise ValueError("topic is required")

    raw_text = str(raw_input or "").strip()

    # Phase 4.7e-a: when the caller asks for loose normalization, parse the
    # raw text once and let parsed values fill in any field the caller did
    # not explicitly supply. Explicit non-empty caller values always win.
    parsed: dict = {}
    if normalize_loose and raw_text:
        parsed = normalize_loose_research_text(raw_text, topic=topic_text)

    explicit_sources = _normalize_sources(sources)
    explicit_key_ideas = _clean_list(key_ideas)
    explicit_risks = _clean_list(risks_or_weaknesses)
    explicit_do_not = _clean_list(do_not_assume)
    explicit_suggested = str(suggested_dream_trial_input or "").strip()

    parsed_sources = _normalize_sources(parsed.get("sources")) if parsed else []
    parsed_key_ideas = _clean_list(parsed.get("key_ideas")) if parsed else []
    parsed_risks = _clean_list(parsed.get("risks_or_weaknesses")) if parsed else []
    parsed_do_not = _clean_list(parsed.get("do_not_assume")) if parsed else []
    parsed_suggested = str(parsed.get("suggested_dream_trial_input") or "").strip() if parsed else ""

    normalized_sources = explicit_sources if explicit_sources else parsed_sources
    normalized_key_ideas = explicit_key_ideas if explicit_key_ideas else parsed_key_ideas
    normalized_risks = explicit_risks if explicit_risks else parsed_risks
    normalized_do_not_assume = explicit_do_not if explicit_do_not else parsed_do_not
    suggested = explicit_suggested if explicit_suggested else parsed_suggested

    if not raw_text and not _has_structured_fields(
        normalized_sources,
        normalized_key_ideas,
        normalized_risks,
        normalized_do_not_assume,
        suggested,
    ):
        raise ValueError("raw_input is required unless structured fields are provided")

    repo_root = _resolve_repo_path(repo_path)
    root = get_agent_dir(str(repo_root)) / "dream_references"
    root.mkdir(parents=True, exist_ok=True)

    now_dt = now or datetime.now()
    base_reference_id = _build_reference_id(now_dt, topic_text)
    reference_id, reference_dir = _allocate_reference_dir(root, base_reference_id)
    reference_dir.mkdir(parents=True, exist_ok=False)

    parsed_summary = (parsed.get("summary") or "").strip() if parsed else ""
    if parsed_summary:
        snippet = parsed_summary if len(parsed_summary) <= 360 else parsed_summary[:360].rstrip() + "..."
        summary = f"Imported notes claim: {snippet}"
    else:
        summary = _build_summary(raw_text, normalized_key_ideas, normalized_sources)
    payload = {
        "reference_id": reference_id,
        "created_at": now_dt.isoformat(timespec="seconds"),
        "topic": topic_text,
        "source_type": _normalize_reference_source_type(source_type),
        "raw_input": raw_text,
        "summary": summary,
        "sources": normalized_sources,
        "key_ideas": normalized_key_ideas,
        "risks_or_weaknesses": normalized_risks,
        "do_not_assume": normalized_do_not_assume,
        "suggested_dream_trial_input": suggested,
        "usable_as_markdown_file": True,
    }

    json_path = reference_dir / "reference.json"
    markdown_path = reference_dir / "reference.md"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    markdown_path.write_text(_render_reference_markdown(payload), encoding="utf-8")

    return DreamReferenceResult(
        reference_id=reference_id,
        reference_dir=str(reference_dir),
        json_path=str(json_path),
        markdown_path=str(markdown_path),
        summary=summary,
    )


def _summarize_reference(reference_dir: Path) -> dict | None:
    json_path = reference_dir / "reference.json"
    if not json_path.is_file():
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    reference_id = str(data.get("reference_id") or reference_dir.name)
    if not REFERENCE_ID_RE.match(reference_id):
        return None
    markdown_path = reference_dir / "reference.md"
    return {
        "reference_id": reference_id,
        "created_at": data.get("created_at", ""),
        "topic": data.get("topic", ""),
        "source_type": data.get("source_type", ""),
        "summary": data.get("summary", ""),
        "source_count": len(data.get("sources") or []),
        "reference_dir": str(reference_dir),
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
    }


def list_dream_references(repo_path) -> list[dict]:
    root = references_root(str(repo_path))
    if not root.is_dir():
        return []

    summaries: list[dict] = []
    for sub in root.iterdir():
        if not sub.is_dir():
            continue
        if not REFERENCE_ID_RE.match(sub.name):
            continue
        summary = _summarize_reference(sub)
        if summary is not None:
            summaries.append(summary)
    summaries.sort(key=lambda item: item.get("reference_id", ""), reverse=True)
    return summaries


def read_dream_reference_file(repo_path, reference_id: str, file_name: str) -> str:
    if file_name not in ALLOWED_REFERENCE_FILES:
        raise ValueError(f"file not allowed: {file_name}")
    if not REFERENCE_ID_RE.match(str(reference_id or "")):
        raise ValueError(f"reference not found: {reference_id}")

    root = references_root(str(repo_path)).resolve()
    reference_dir = (root / reference_id).resolve()
    try:
        reference_dir.relative_to(root)
    except ValueError:
        raise ValueError("reference path escapes dream_references root")
    if not reference_dir.is_dir():
        raise FileNotFoundError(f"reference not found: {reference_id}")

    target = (reference_dir / file_name).resolve()
    try:
        target.relative_to(reference_dir)
    except ValueError:
        raise ValueError("file path escapes reference directory")
    if not target.is_file():
        raise FileNotFoundError(f"file not found: {file_name}")
    return target.read_text(encoding="utf-8")

