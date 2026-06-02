"""Phase 5P.1 — a tiny, safe Markdown renderer for the Dream report viewer.

The Dream report modal used to dump ``morning_report.txt`` into a raw ``<pre>``
block. This module renders that Markdown into readable HTML for the viewer.

Design constraints (Phase 5P.1):
- **Escape HTML by default.** Every piece of text content is HTML-escaped
  exactly once before any tag is emitted, so raw ``<script>`` / ``<img onerror>``
  payloads in a report can never execute — they show up as literal text.
- **No raw HTML passthrough.** Unlike ``markdown.markdown`` (which lets raw
  HTML through, and double-escapes code spans when its input is pre-escaped),
  this renderer only ever emits the small, fixed set of tags below.
- **No external/JS dependencies.** Pure string work; safe to import anywhere.

Supported subset: ATX headings, paragraphs, unordered + ordered lists (with
one-level nesting by indentation), fenced code blocks, inline code, ``**bold**``
and ``_italic_``, and simple GitHub-style pipe tables. Anything else degrades to
escaped paragraph text.
"""
from __future__ import annotations

import re

__all__ = ["render_dream_report_markdown"]


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# Leading indent, a bullet (-, *, +) or "N." ordered marker, then the content.
_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.*)$")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\w)_([^_\n]+)_(?!\w)")
_CODE_PLACEHOLDER = "\x00CODE{0}\x00"


def render_dream_report_markdown(text: str | None) -> str:
    """Render a Markdown ``text`` into safe HTML for the Dream report viewer.

    Returns an empty string for empty / ``None`` input. The output only ever
    contains the small fixed tag set this module emits; all text is escaped.
    """
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        # Fenced code block — content is escaped, never interpreted.
        if line.strip().startswith("```"):
            i += 1
            code_lines: list[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # consume the closing fence (or run off the end safely)
            escaped = _escape("\n".join(code_lines))
            blocks.append(f"<pre><code>{escaped}</code></pre>")
            continue

        # ATX heading.
        heading = _HEADING_RE.match(line.strip())
        if heading:
            level = len(heading.group(1))
            blocks.append(
                f"<h{level}>{_render_inline(heading.group(2).strip())}</h{level}>"
            )
            i += 1
            continue

        # Pipe table — a header row followed by a |---|---| separator.
        if "|" in line and i + 1 < n and _is_table_separator(lines[i + 1]):
            table_html, i = _render_table(lines, i)
            blocks.append(table_html)
            continue

        # List (ordered or unordered, with one level of indented nesting).
        if _LIST_RE.match(line):
            items: list[tuple[int, str, str]] = []
            while i < n and _LIST_RE.match(lines[i]):
                m = _LIST_RE.match(lines[i])
                indent = len(m.group(1).replace("\t", "    "))
                list_type = "ol" if re.match(r"\d+\.", m.group(2)) else "ul"
                items.append((indent, list_type, m.group(3)))
                i += 1
            # A run of same-type items at the same indent forms one list; a
            # marker switch (ul<->ol) or a shallower indent starts a sibling
            # list. _render_list returns the index of the first item it did NOT
            # consume, so loop until every item is rendered — otherwise content
            # after a marker switch is silently dropped.
            pos = 0
            while pos < len(items):
                list_html, pos = _render_list(items, pos, items[pos][0])
                blocks.append(list_html)
            continue

        # Paragraph — gather consecutive lines until a blank or a new block.
        para_lines: list[str] = []
        while i < n and lines[i].strip() and not _starts_block(lines, i):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            blocks.append(f"<p>{_render_inline(' '.join(para_lines))}</p>")
        else:
            # Defensive: never spin without consuming a line.
            i += 1

    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _escape(s: str) -> str:
    """HTML-escape once. Applied to every text fragment before emitting tags."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_inline(s: str) -> str:
    """Escape then apply inline code / bold / italic. Code is escaped once."""
    s = _escape(s)
    codes: list[str] = []

    def _stash(match: "re.Match[str]") -> str:
        codes.append(match.group(1))
        return _CODE_PLACEHOLDER.format(len(codes) - 1)

    s = _INLINE_CODE_RE.sub(_stash, s)
    s = _BOLD_RE.sub(r"<strong>\1</strong>", s)
    s = _ITALIC_RE.sub(r"<em>\1</em>", s)
    for idx, code in enumerate(codes):
        s = s.replace(_CODE_PLACEHOLDER.format(idx), f"<code>{code}</code>")
    return s


def _starts_block(lines: list[str], i: int) -> bool:
    """True if ``lines[i]`` begins a non-paragraph block."""
    line = lines[i]
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("```"):
        return True
    if _HEADING_RE.match(stripped):
        return True
    if _LIST_RE.match(line):
        return True
    if "|" in line and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
        return True
    return False


def _render_list(
    items: list[tuple[int, str, str]], start: int, base_indent: int
) -> tuple[str, int]:
    """Render list ``items`` at ``base_indent`` into HTML; return (html, next)."""
    list_type = items[start][1]
    out = [f"<{list_type}>"]
    i = start
    while i < len(items):
        indent, item_type, content = items[i]
        if indent < base_indent:
            break
        if indent > base_indent:
            # Deeper item with no parent at this level — nest it directly.
            sub_html, i = _render_list(items, i, indent)
            out.append(sub_html)
            continue
        if item_type != list_type:
            break  # a different marker at the same level starts a new list
        li = _render_inline(content)
        i += 1
        if i < len(items) and items[i][0] > base_indent:
            sub_html, i = _render_list(items, i, items[i][0])
            li += sub_html
        out.append(f"<li>{li}</li>")
    out.append(f"</{list_type}>")
    return "".join(out), i


def _is_table_separator(line: str) -> bool:
    """True for a Markdown table separator row like ``| --- | :--: |``."""
    s = line.strip()
    if "-" not in s:
        return False
    return bool(re.fullmatch(r"\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?", s))


def _split_row(row: str) -> list[str]:
    """Split a pipe-table row into trimmed cells, dropping edge pipes."""
    cells = row.strip().split("|")
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _render_table(lines: list[str], i: int) -> tuple[str, int]:
    """Render a pipe table starting at ``lines[i]``; return (html, next index)."""
    header = _split_row(lines[i])
    j = i + 2  # skip header + separator
    body: list[list[str]] = []
    n = len(lines)
    while j < n and lines[j].strip() and "|" in lines[j]:
        body.append(_split_row(lines[j]))
        j += 1
    out = ["<table>", "<thead>", "<tr>"]
    out += [f"<th>{_render_inline(c)}</th>" for c in header]
    out += ["</tr>", "</thead>", "<tbody>"]
    for row in body:
        out.append("<tr>")
        out += [f"<td>{_render_inline(c)}</td>" for c in row]
        out.append("</tr>")
    out += ["</tbody>", "</table>"]
    return "".join(out), j
