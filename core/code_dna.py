# core/code_dna.py
"""Code DNA — fingerprint a repo's coding style so the AI can match it.

Backward-compatible: the original `compute_dna(repo_path)` and
`dna_to_prompt_block(dna)` keep their original return shapes (existing tests /
callers stay valid), but `compute_dna` now also fills in extra fields
(`brace_style`, `comment_style`, `language_mix`, `avg_func_length`, `file_count`).

New helpers:
  save_dna(repo_path, dna)      — persist to .agent/<tag>/code_dna.json
  load_dna(repo_path)           — read the cached JSON, return None if missing
  get_or_compute_dna(repo_path) — load-cache-or-compute-and-save

Friction toggle:
  dna_to_prompt_block(dna, mode="match")    — default — emit the style block
  dna_to_prompt_block(dna, mode="ignore")   — emit a "use idiomatic style"
                                              hint instead of locking to repo DNA
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Optional
import json
import re

from core.credential_redaction import redact_credentials
# INDENT.RUNTIME.1 repair seam: the one semantic authority a future patch to
# `_classify_indent` may use instead of inventing a parser. Not called by the
# current (deliberately unfixed) body below — see
# docs/designs/2026-09-12-language-context-transport-and-repair-boundary.md.
from core.indentation_observation import (
    assess_indentation_observation,
    observe_source_indentation,
)

if TYPE_CHECKING:
    from core.repository_inventory import RepositoryInventory


# ---------------------------------------------------------------------------
# Extension allowlist — defer to config so adding a language anywhere picks
# up here too. Stays correct after Go/Java/Kotlin were added to LANGUAGE_MAP.
# ---------------------------------------------------------------------------
def _code_extensions() -> set[str]:
    try:
        from config import LANGUAGE_MAP
        non_code = {"document", "text", "json"}
        return {ext for ext, lang in LANGUAGE_MAP.items() if lang not in non_code}
    except Exception:
        return {
            ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
            ".c", ".h", ".cpp", ".cxx", ".cc", ".hpp", ".hxx",
            ".cs", ".rs", ".go", ".java", ".kt", ".kts",
            ".html", ".css",
        }


# ---------------------------------------------------------------------------
# Function-name regex per family. Keeps naming detection accurate across
# C#/Java/Kotlin which don't have a leading `def`/`fn` keyword.
# ---------------------------------------------------------------------------
_FUNC_RES = [
    # Python / TS / JS / Rust / Go: leading keyword + name
    re.compile(r"\b(?:def|function|fn|func)\s+([A-Za-z_][\w]*)"),
    # C# / Java / Kotlin / C++ methods: modifier* type Name(
    # Heuristic — matches `public void Move(`, `private static int Foo(`, etc.
    re.compile(
        r"\b(?:public|private|protected|internal|static|final|virtual|"
        r"override|async|abstract|sealed|inline|suspend)\s+"
        r"(?:[\w<>,\[\]\s\?]+\s+)?"
        r"([A-Za-z_]\w*)\s*\(",
    ),
    # Kotlin `fun name(` (also matches above but kept explicit for clarity)
    re.compile(r"\bfun\s+([A-Za-z_]\w*)"),
]


def _language_for_suffix(suffix: str) -> Optional[str]:
    """The same authoritative extension->language label compute_dna's own
    lang_mix already keys on suffix for (INDENT.RUNTIME.1) — never a second
    suffix->language map. None for an unmapped or unresolvable extension."""
    try:
        from config import LANGUAGE_MAP
    except Exception:
        return None
    return LANGUAGE_MAP.get(suffix.lower())


def _classify_name(name: str) -> str:
    """snake_case / camelCase / PascalCase. Falls back to 'mixed' otherwise."""
    if "_" in name and name.lower() == name:
        return "snake"
    if name and name[0].isupper():
        return "pascal"
    if name and name[0].islower() and any(c.isupper() for c in name[1:]):
        return "camel"
    return "mixed"


def _classify_indent(text: str, *, language: str | None = None) -> Optional[str]:
    """Return one of '2space', '4space', 'tab', or None when no leading
    indent on any line. We bias toward the ratio of indented lines so a single
    tab in a Python file doesn't outvote a thousand 4-space lines.

    ``language`` describes the language of ``text`` (INDENT.RUNTIME.1) and is
    currently ignored by this body; the classification below is unchanged."""
    counts = Counter()
    for line in text.splitlines():
        if not line or line[0] not in " \t":
            continue
        if line.startswith("\t"):
            counts["tab"] += 1
        elif line.startswith("    "):
            counts["4space"] += 1
        elif line.startswith("  "):
            counts["2space"] += 1
    return counts.most_common(1)[0][0] if counts else None


def _classify_brace(text: str) -> Optional[str]:
    """Allman = `{` on its own line. K&R = `{` at end of signature line.
    Returns None for languages without braces (Python)."""
    if "{" not in text:
        return None
    allman = len(re.findall(r"^\s*\{\s*$", text, re.M))
    knr = len(re.findall(r"\)\s*\{\s*$", text, re.M))
    if allman + knr < 3:
        return None  # not enough samples to be confident
    return "allman" if allman > knr else "k_and_r"


def _classify_comment_style(text: str) -> Optional[str]:
    """`//` (C-family), `#` (Python/Ruby/shell), `/* */` block, or 'mixed'."""
    slash = len(re.findall(r"^\s*//", text, re.M))
    hash_ = len(re.findall(r"^\s*#", text, re.M))
    block = len(re.findall(r"/\*", text))
    total = slash + hash_ + block
    if total < 5:
        return None
    top = max(("slash", slash), ("hash", hash_), ("block", block), key=lambda x: x[1])
    if top[1] / total > 0.7:
        return top[0]
    return "mixed"


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------
def compute_dna(
    repo_path: str,
    *,
    inventory: "RepositoryInventory | None" = None,
) -> dict:
    """Walk the repo, return a style-fingerprint dict.

    Output dict keys (all stable / safe to read):
      indent          : "2space" | "4space" | "tab" | "unknown"
      naming          : "snake" | "camel" | "pascal" | "mixed" | "unknown"
      max_line_pref   : int (95th percentile line length, or 100 fallback)
      func_count      : int
      avg_func_length : int (line count, rough)
      brace_style     : "allman" | "k_and_r" | None
      comment_style   : "slash" | "hash" | "block" | "mixed" | None
      language_mix    : {extension: count}
      file_count      : int
    """
    code_exts = _code_extensions()

    indents = Counter()
    naming = Counter()
    line_lengths: list[int] = []
    func_lengths: list[int] = []
    total_funcs = 0
    file_count = 0
    lang_mix: Counter = Counter()
    brace_votes = Counter()
    comment_votes = Counter()

    repo_root = Path(repo_path).expanduser().resolve()
    from core.repository_inventory import (
        create_repository_inventory,
        validate_repository_inventory,
    )

    if inventory is not None:
        operation_inventory = validate_repository_inventory(
            repo_root,
            inventory,
        )
    elif not repo_root.is_dir():
        return _empty_dna()
    else:
        operation_inventory = create_repository_inventory(repo_root)

    if not repo_root.is_dir():
        return _empty_dna()

    for entry in operation_inventory.indexable_entries:
        p = entry.absolute_path
        if p.suffix.lower() not in code_exts:
            continue

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        file_count += 1
        lang_mix[p.suffix.lower()] += 1

        # Per-line stats
        for line in text.splitlines():
            line_lengths.append(len(line))

        # Indent detection (per-file, vote across files). INDENT.RUNTIME.1:
        # language describes this walked file, never core/code_dna.py itself.
        ind = _classify_indent(text, language=_language_for_suffix(p.suffix))
        if ind:
            indents[ind] += 1

        # Brace + comment style (per-file)
        bs = _classify_brace(text)
        if bs:
            brace_votes[bs] += 1
        cs = _classify_comment_style(text)
        if cs:
            comment_votes[cs] += 1

        # Function names + rough length
        last_idx = -1
        for fre in _FUNC_RES:
            for m in fre.finditer(text):
                name = m.group(1)
                naming[_classify_name(name)] += 1
                total_funcs += 1
                # Rough length: distance to next function start, capped at 200.
                start = m.start()
                if last_idx >= 0:
                    func_lengths.append(min(200, text[last_idx:start].count("\n")))
                last_idx = start

    if not line_lengths:
        return _empty_dna()

    line_lengths.sort()
    p95 = line_lengths[int(len(line_lengths) * 0.95)]
    avg_func_len = (sum(func_lengths) // len(func_lengths)) if func_lengths else 0

    return {
        "indent": indents.most_common(1)[0][0] if indents else "unknown",
        "naming": naming.most_common(1)[0][0] if naming else "unknown",
        "max_line_pref": int(p95) if p95 > 0 else 100,
        "func_count": total_funcs,
        "avg_func_length": int(avg_func_len),
        "brace_style": brace_votes.most_common(1)[0][0] if brace_votes else None,
        "comment_style": comment_votes.most_common(1)[0][0] if comment_votes else None,
        "language_mix": dict(lang_mix.most_common()),
        "file_count": file_count,
    }


def _empty_dna() -> dict:
    return {
        "indent": "unknown",
        "naming": "unknown",
        "max_line_pref": 100,
        "func_count": 0,
        "avg_func_length": 0,
        "brace_style": None,
        "comment_style": None,
        "language_mix": {},
        "file_count": 0,
    }


# ---------------------------------------------------------------------------
# Persistence — cache to .agent/<tag>/code_dna.json so re-runs are instant.
# ---------------------------------------------------------------------------
def save_dna(repo_path: str, dna: dict) -> Optional[Path]:
    try:
        from config import get_agent_dir
        out = get_agent_dir(repo_path) / "code_dna.json"
        out.write_text(json.dumps(dna, ensure_ascii=False, indent=2), encoding="utf-8")
        return out
    except Exception as e:
        print(f"⚠️ save_dna failed: {redact_credentials(e)}")
        return None


def load_dna(repo_path: str) -> Optional[dict]:
    try:
        from config import get_agent_dir
        path = get_agent_dir(repo_path) / "code_dna.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_or_compute_dna(
    repo_path: str,
    force: bool = False,
    *,
    inventory: "RepositoryInventory | None" = None,
) -> dict:
    """Convenience: return cached DNA if it exists, otherwise compute + save."""
    if inventory is not None:
        from core.repository_inventory import (
            validate_repository_inventory,
        )

        validate_repository_inventory(repo_path, inventory)
        # The on-disk compatibility cache has no inventory/freshness token.
        # A caller supplying an operation snapshot therefore requires a fresh
        # projection from that snapshot.
        dna = compute_dna(repo_path, inventory=inventory)
        save_dna(repo_path, dna)
        return dna
    if not force:
        cached = load_dna(repo_path)
        if cached:
            return cached
    dna = compute_dna(repo_path, inventory=inventory)
    save_dna(repo_path, dna)
    return dna


# ---------------------------------------------------------------------------
# Prompt block — friction toggle
# ---------------------------------------------------------------------------
def dna_to_prompt_block(dna: dict, mode: str = "match") -> str:
    """Format DNA as a one-line prompt hint.

    mode="match"  → tell the AI to mirror this repo's style (default)
    mode="ignore" → tell the AI to use idiomatic style instead (escape hatch)
    """
    if mode == "ignore":
        return (
            "REPO STYLE: ignored for this run. Use the language's idiomatic style "
            "in patched_snippet (clean, conventional, not necessarily matching repo)."
        )

    if not dna or dna.get("file_count", 0) == 0:
        return "REPO STYLE: not yet fingerprinted. Use idiomatic style for the language."

    parts = [f"indent={dna.get('indent', 'unknown')}"]

    naming = dna.get("naming")
    if naming and naming != "unknown":
        parts.append(f"naming={naming}")

    line_pref = dna.get("max_line_pref")
    if line_pref:
        parts.append(f"line~{line_pref}c")

    brace = dna.get("brace_style")
    if brace:
        parts.append(f"brace={brace}")

    comment = dna.get("comment_style")
    if comment:
        parts.append(f"comment={comment}")

    avg = dna.get("avg_func_length", 0)
    if avg and avg > 0:
        parts.append(f"avg_func~{avg}l")

    return "REPO STYLE: " + ", ".join(parts) + ". Match this in patched_snippet."
