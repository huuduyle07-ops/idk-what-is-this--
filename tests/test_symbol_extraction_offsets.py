"""RETRIEVE.LIVE.1 - symbol extraction must not corrupt names on non-ASCII source.

The reproduced production defect: ``parse_code_with_treesitter`` parsed a UTF-8
*byte* buffer (``parser.parse(bytes(code, "utf8"))``) and then sliced every
extracted span out of the Python ``str``.  Byte offsets index characters only
while a file is pure ASCII.  One non-ASCII character - an em dash in a
docstring, an emoji in a log line - shifts every later offset, so every symbol
and call name extracted after it is a misaligned fragment of the source.

Real examples captured from this repository before the fix::

    agents/deepseek_client.py::cont          (the real symbol is ``main``)
    call::e(\\n
    call::n<warning emoji> O
    core/code_dna.py::"() -> set[str]:\\n"   (12 of 12 symbols corrupt)

The byte contract itself is correct, and is what the rest of production already
assumes - ``patching/patch_engine.py`` slices ``code_bytes[node["start"]:
node["end"]]``.  Only extraction disagreed with it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.treesitter_parse import (
    SYMBOL_EXTRACTION_VERSION,
    parse_code_with_treesitter,
)


RESIDUE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f()\[\]{}\"']")


def _names(parsed: dict) -> list[str]:
    return [symbol.get("name") for symbol in parsed.get("symbols", [])]


def _calls(parsed: dict) -> list[str]:
    found: list[str] = []
    for symbol in parsed.get("symbols", []):
        found.extend(symbol.get("calls") or [])
    return found


def _requires_python_parser() -> None:
    parsed = parse_code_with_treesitter("def probe():\n    return 1\n", "python")
    if "probe" not in _names(parsed):
        pytest.skip("tree-sitter python grammar unavailable in this environment")


# ---------------------------------------------------------------------------
# The reproduced corruption mechanism
# ---------------------------------------------------------------------------

def test_non_ascii_docstring_does_not_shift_later_symbol_names():
    _requires_python_parser()
    source = (
        '"""Header — an em dash makes bytes and characters disagree."""\n'
        "\n"
        "def _classify_indent(text):\n"
        "    return '4space'\n"
        "\n"
        "def main():\n"
        "    return _classify_indent('')\n"
    )

    names = _names(parse_code_with_treesitter(source, "python"))

    assert "_classify_indent" in names
    assert "main" in names


def test_emoji_in_a_log_line_does_not_corrupt_the_following_call_names():
    _requires_python_parser()
    source = (
        "def run():\n"
        '    print("⚠️ warning")\n'
        "    handle_result()\n"
        "    return finish()\n"
    )

    calls = _calls(parse_code_with_treesitter(source, "python"))

    assert "handle_result" in calls
    assert "finish" in calls
    assert not [call for call in calls if RESIDUE.search(call)]


def test_every_extracted_name_is_free_of_structural_extraction_residue():
    """Population-level property: no fragment carries syntax or newlines."""
    _requires_python_parser()
    source = (
        "# 你好 — mixed-width comment\n"
        "class CafeStore:\n"
        "    def brew(self):\n"
        '        return self.pull("☕")\n'
        "\n"
        "def circle_area(r):\n"
        "    return 3.14 * r * r\n"
    )

    parsed = parse_code_with_treesitter(source, "python")

    for name in _names(parsed):
        if name == "<top-level>":
            continue
        assert not RESIDUE.search(name), name
    for call in _calls(parsed):
        assert not RESIDUE.search(call), call


def test_symbol_content_matches_the_declared_byte_span():
    """``start``/``end`` are byte offsets; ``content`` must agree with them.

    ``patching/patch_engine.py`` already slices the encoded buffer with these
    offsets, so extraction agreeing with them is what keeps a patch anchored to
    the symbol it claims to edit.
    """
    _requires_python_parser()
    source = (
        "Ä = 1  # non-ASCII ahead of the function shifts every later offset\n"
        "def target(value):\n"
        "    return value\n"
    )
    raw = source.encode("utf-8")

    parsed = parse_code_with_treesitter(source, "python")
    symbol = next(s for s in parsed["symbols"] if s["name"] == "target")

    assert symbol["content"] == raw[symbol["start"]:symbol["end"]].decode("utf-8")
    assert symbol["content"].startswith("def target")


def test_execution_flow_text_stays_decodable_next_to_a_multibyte_character():
    _requires_python_parser()
    source = (
        "def flow():\n"
        '    label = "———"\n'
        "    if label:\n"
        "        return label\n"
        "    return None\n"
    )

    parsed = parse_code_with_treesitter(source, "python")
    flow = next(s for s in parsed["symbols"] if s["name"] == "flow")["execution_flow"]

    assert flow
    for step in flow:
        assert "�" not in step["text"]
        assert "�" not in step["context"]


# ---------------------------------------------------------------------------
# Legitimate symbols must survive (no over-correction)
# ---------------------------------------------------------------------------

def test_ascii_python_symbols_are_unchanged():
    _requires_python_parser()
    source = (
        "class Calc:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
        "\n"
        "def subtract(a, b):\n"
        "    return a - b\n"
    )

    names = _names(parse_code_with_treesitter(source, "python"))

    assert "Calc" in names
    assert "add" in names
    assert "subtract" in names


def test_nested_functions_are_still_extracted():
    _requires_python_parser()
    source = (
        "def outer():\n"
        "    def inner():\n"
        "        return 1\n"
        "    return inner()\n"
    )

    names = _names(parse_code_with_treesitter(source, "python"))

    assert "outer" in names
    assert "inner" in names


def test_unicode_identifier_is_preserved_exactly():
    _requires_python_parser()
    source = "def élévation(r):\n    return r\n"

    names = _names(parse_code_with_treesitter(source, "python"))

    assert "élévation" in names


def test_typescript_function_and_method_names_survive_non_ascii_source():
    probe = parse_code_with_treesitter(
        "export function ok(): number { return 1; }\n", "typescript"
    )
    if "ok" not in _names(probe):
        pytest.skip("tree-sitter typescript grammar unavailable")

    source = (
        "// cafe — non-ASCII comment\n"
        "export function loadUser(id: string): string {\n"
        "  return fetchUser(id);\n"
        "}\n"
        "\n"
        "export class Store {\n"
        "  save(value: string): void {\n"
        "    this.write(value);\n"
        "  }\n"
        "}\n"
    )

    parsed = parse_code_with_treesitter(source, "typescript")
    names = _names(parsed)

    assert "loadUser" in names
    assert "save" in names
    assert "fetchUser" in _calls(parsed)


def test_valid_callsite_survives_and_stays_attached_to_its_caller():
    _requires_python_parser()
    source = (
        "def helper():\n"
        "    return 1\n"
        "\n"
        "def caller():\n"
        "    return helper()\n"
    )

    parsed = parse_code_with_treesitter(source, "python")
    caller = next(s for s in parsed["symbols"] if s["name"] == "caller")

    assert "helper" in caller["calls"]


def test_imports_are_extracted_from_source_with_non_ascii_above_them():
    _requires_python_parser()
    source = (
        "# —\n"
        "import os\n"
        "from pathlib import Path\n"
    )

    imports = parse_code_with_treesitter(source, "python")["imports"]

    assert "os" in imports
    assert "pathlib" in imports


# ---------------------------------------------------------------------------
# Freshness: extraction semantics are versioned
# ---------------------------------------------------------------------------

def test_symbol_extraction_version_is_a_nonempty_string():
    assert isinstance(SYMBOL_EXTRACTION_VERSION, str)
    assert SYMBOL_EXTRACTION_VERSION.strip()
