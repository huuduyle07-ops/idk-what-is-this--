"""Phase 4.7e-b — Title-only Source Capture.

The loose normalizer must keep title-only lines (the Zapier output sometimes
omits URLs) as honest, low-confidence source entries instead of dropping
them. Each title-only entry must:
  - have url == ""
  - have source_type == "unknown" and reliability == "unknown"
  - carry a why_relevant warning naming the missing URL
  - be deduplicated against other title-only entries by normalized title
  - be skipped when a URL-based source with the same title already exists
    (the URL source is preferred)

Existing URL-based parsing and dedup behavior must keep working.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import dream_references


TITLE_ONLY_NOTES = """
Research Results

Summary:
Brief context about Unix text-search tools.

Key Papers & Articles:
- The Unix Programming Environment
- grep: A Pattern Matching Utility
- Regular Expressions: A Complete Introduction
- Efficient Text Searching
- The Unix Programming Environment

Resources & Links:
- https://www.gnu.org/software/grep/manual/grep.html
- Resources & Links:
- ---
- ab

Key Insights:
- Boyer-Moore is great for literals.

Suggested Dream Trial Input:
Pick one of these references and try a tiny pilot.
"""


MIXED_NOTES = """
Key Papers & Articles:
- The Pragmatic Programmer
- https://example.test/article - The Pragmatic Programmer
- A completely different book
"""


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    refs_root = dream_references.references_root(str(r))
    if refs_root.exists():
        for sub in refs_root.iterdir():
            if sub.is_dir():
                for f in sub.iterdir():
                    try:
                        f.unlink()
                    except OSError:
                        pass
                try:
                    sub.rmdir()
                except OSError:
                    pass
    yield r


# ---------------------------------------------------------------------------
# 1. Title-only lines become source entries
# ---------------------------------------------------------------------------

def test_title_only_zapier_lines_become_source_entries():
    parsed = dream_references.normalize_loose_research_text(
        TITLE_ONLY_NOTES, topic="grep",
    )
    titles = [s["title"] for s in parsed["sources"]]
    assert "The Unix Programming Environment" in titles
    assert "grep: A Pattern Matching Utility" in titles
    assert "Regular Expressions: A Complete Introduction" in titles
    assert "Efficient Text Searching" in titles


# ---------------------------------------------------------------------------
# 2. Title-only sources have empty URL
# ---------------------------------------------------------------------------

def test_title_only_sources_have_empty_url():
    parsed = dream_references.normalize_loose_research_text(
        TITLE_ONLY_NOTES, topic="grep",
    )
    title_only = [s for s in parsed["sources"] if not s["url"]]
    assert title_only, parsed["sources"]
    for source in title_only:
        assert source["url"] == ""


# ---------------------------------------------------------------------------
# 3. Title-only sources are low-confidence
# ---------------------------------------------------------------------------

def test_title_only_sources_are_low_confidence():
    parsed = dream_references.normalize_loose_research_text(
        TITLE_ONLY_NOTES, topic="grep",
    )
    title_only = [s for s in parsed["sources"] if not s["url"]]
    assert title_only
    for source in title_only:
        assert source["source_type"] == "unknown"
        assert source["reliability"] == "unknown"


# ---------------------------------------------------------------------------
# 4. Title-only sources include why_relevant warning
# ---------------------------------------------------------------------------

def test_title_only_sources_carry_missing_url_warning():
    parsed = dream_references.normalize_loose_research_text(
        TITLE_ONLY_NOTES, topic="grep",
    )
    title_only = [s for s in parsed["sources"] if not s["url"]]
    assert title_only
    for source in title_only:
        why = (source.get("why_relevant") or "").lower()
        assert "title-only" in why
        assert "url" in why and "missing" in why


# ---------------------------------------------------------------------------
# 5. Duplicate title-only lines are deduplicated
# ---------------------------------------------------------------------------

def test_duplicate_title_only_lines_are_deduplicated():
    parsed = dream_references.normalize_loose_research_text(
        TITLE_ONLY_NOTES, topic="grep",
    )
    titles = [s["title"] for s in parsed["sources"] if not s["url"]]
    assert titles.count("The Unix Programming Environment") == 1


def test_title_only_dedup_is_case_and_whitespace_insensitive():
    notes = """
Key Papers & Articles:
- The Pragmatic Programmer
- the   pragmatic  programmer
- THE PRAGMATIC PROGRAMMER
"""
    parsed = dream_references.normalize_loose_research_text(notes, topic="x")
    title_only = [s for s in parsed["sources"] if not s["url"]]
    assert len(title_only) == 1, [s["title"] for s in title_only]


# ---------------------------------------------------------------------------
# 6. URL-based source parsing still works
# ---------------------------------------------------------------------------

def test_url_based_source_parsing_still_works():
    parsed = dream_references.normalize_loose_research_text(
        TITLE_ONLY_NOTES, topic="grep",
    )
    urls = [s["url"] for s in parsed["sources"] if s["url"]]
    assert "https://www.gnu.org/software/grep/manual/grep.html" in urls


# ---------------------------------------------------------------------------
# 7. URL-based duplicate behavior still works
# ---------------------------------------------------------------------------

def test_url_based_duplicate_behavior_still_works():
    notes = """
Key Papers & Articles:
- https://www.gnu.org/software/grep/manual/grep.html
- https://www.gnu.org/software/grep/manual/grep.html

Resources & Links:
- https://www.gnu.org/software/grep/manual/grep.html
"""
    parsed = dream_references.normalize_loose_research_text(notes, topic="grep")
    gnu = [s for s in parsed["sources"] if "gnu.org/software/grep" in s["url"]]
    assert len(gnu) == 1, parsed["sources"]


def test_url_source_preferred_over_title_only_with_same_title():
    """When a title-only line has the same title as a URL source, the URL
    source wins and the bare title is dropped (no synthetic duplicate)."""
    parsed = dream_references.normalize_loose_research_text(MIXED_NOTES, topic="x")
    pragmatic = [s for s in parsed["sources"] if "pragmatic" in s["title"].lower()]
    # One URL-based entry; the duplicate title-only line is suppressed.
    assert len(pragmatic) == 1, parsed["sources"]
    assert pragmatic[0]["url"].startswith("https://")
    # The other title-only line ("A completely different book") is still kept.
    other = [s for s in parsed["sources"] if "completely different" in s["title"].lower()]
    assert len(other) == 1


# ---------------------------------------------------------------------------
# 8. reference.md renders URL: _missing_ for title-only sources
# ---------------------------------------------------------------------------

def test_reference_md_renders_title_only_url_as_missing(repo):
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="title-only render",
        raw_input=TITLE_ONLY_NOTES,
        normalize_loose=True,
    )
    md = Path(result.markdown_path).read_text(encoding="utf-8")
    assert "URL: _missing_" in md, md
    # The conservative warnings still appear (Phase 4.7e-a invariant).
    assert "Imported research was not independently verified." in md
    # The well-formed URL source still renders with its URL, not _missing_.
    assert "https://www.gnu.org/software/grep/manual/grep.html" in md


def test_reference_json_keeps_title_only_entries_distinct_from_url_entries(repo):
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="title-only json",
        raw_input=TITLE_ONLY_NOTES,
        normalize_loose=True,
    )
    data = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    url_sources = [s for s in data["sources"] if s["url"]]
    title_only = [s for s in data["sources"] if not s["url"]]
    assert url_sources, data["sources"]
    assert title_only, data["sources"]
    # The well-formed URL is preserved.
    assert any(
        s["url"] == "https://www.gnu.org/software/grep/manual/grep.html"
        for s in url_sources
    )


# ---------------------------------------------------------------------------
# Noise filtering
# ---------------------------------------------------------------------------

def test_separator_and_label_and_short_lines_are_not_captured_as_sources():
    parsed = dream_references.normalize_loose_research_text(
        TITLE_ONLY_NOTES, topic="grep",
    )
    titles = [s["title"] for s in parsed["sources"]]
    # The separator "---", the label "Resources & Links:", and the short
    # "ab" line must not have produced a source entry.
    assert all("---" not in t for t in titles)
    assert not any(t.strip().lower() in {"resources & links", "resources and links"} for t in titles)
    assert "ab" not in titles


def test_markdown_heading_inside_section_is_not_captured():
    notes = """
Key Papers & Articles:
- The Pragmatic Programmer
# Stray heading inside the section
"""
    parsed = dream_references.normalize_loose_research_text(notes, topic="x")
    titles = [s["title"] for s in parsed["sources"]]
    assert all("Stray heading" not in t for t in titles)


# ---------------------------------------------------------------------------
# 9. No network/fetch imports added
# ---------------------------------------------------------------------------

def test_no_network_or_fetch_imports_added():
    src = Path(dream_references.__file__).read_text(encoding="utf-8").lower()
    for needle in ("requests", "httpx", "urllib", "aiohttp", "socket"):
        assert needle not in src, f"network import leaked: {needle}"
