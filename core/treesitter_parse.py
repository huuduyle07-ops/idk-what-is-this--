import sys
import re
import os
import json
from pathlib import Path


# Add project root to sys.path to allow importing config.py
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from config import TREESITTER_LANG_MAP

#: Re-exported beside the extraction code it describes.  The constant itself
#: lives in ``core.source_file_policy`` so that pure modules - the repository
#: ignore-policy fingerprint among them - can read it without importing
#: application configuration.
from core.source_file_policy import SYMBOL_EXTRACTION_VERSION  # noqa: F401


def _decode_span(source: bytes, start: int, end: int) -> str:
    """Decode ``source[start:end]``, snapping to UTF-8 character boundaries.

    Tree-sitter node boundaries always fall on character boundaries, so the
    snapping only matters for the deliberately approximate context windows
    (``start - 60`` / ``end + 60``) that ``extract_execution_flow`` takes.
    Snapping there keeps a window from splitting a multi-byte character and
    emitting a replacement character into evidence text.
    """
    start = max(0, min(start, len(source)))
    end = max(start, min(end, len(source)))

    # 0b10xxxxxx is a UTF-8 continuation byte: walk off it in both directions.
    while start > 0 and (source[start] & 0xC0) == 0x80:
        start -= 1
    while end < len(source) and (source[end] & 0xC0) == 0x80:
        end += 1

    return source[start:end].decode("utf-8", errors="replace")


def parse_code_with_treesitter(code: str, language: str):
    try:
        lang_key = TREESITTER_LANG_MAP.get(language.lower())

        if not lang_key:
            return {"symbols": [], "imports": [], "calls": []}

        try:
            from tree_sitter_language_pack import get_parser
            parser = get_parser(lang_key)
        except Exception:
            return {"symbols": [], "imports": [], "calls": []}

        if not hasattr(parser, "parse"):
            raise RuntimeError(
                f"Tree-sitter parser for {language} has no parse() method"
            )

        # Every offset tree-sitter reports indexes THIS buffer, so every span
        # below is sliced out of it.  Slicing ``code`` instead silently
        # corrupts extraction from the first non-ASCII character onward.
        source = bytes(code, "utf8")
        tree = parser.parse(source)
        root = tree.root_node

        symbols = []
        imports = []
        calls = []
    except Exception as e:
        print(f"⚠️ Tree-sitter unavailable for {language}: {e}")
        return {
            "symbols": [],
            "imports": [],
            "calls": [],
        }

    def extract_execution_flow(node, source):
        flow = []

        interesting = {
            "if_statement": "branch",
            "elif_clause": "branch",
            "else_clause": "branch",
            "for_statement": "loop",
            "while_statement": "loop",
            "return_statement": "return",
            "assignment": "assignment",
            "augmented_assignment": "assignment",
            "expression_statement": "expression",
        }

        def short(n, max_len=160):
            text = _decode_span(source, n.start_byte, n.end_byte).strip()
            text = " ".join(text.split())
            return text[:max_len]

        def walk_flow(n):
            if n.type in interesting:
                flow.append({
                    "type": interesting[n.type],
                    "node_type": n.type,
                    "text": short(n),
                    "context": _decode_span(
                        source, n.start_byte - 60, n.end_byte + 60
                    ),
                    "start": n.start_byte,
                    "end": n.end_byte,
                })

            for child in n.children:
                walk_flow(child)

        walk_flow(node)
        flow = sorted(flow, key=lambda x: x["start"])
        return flow[:20]

    def walk(node):
        # Functions / Methods
        if node.type in [
            "function_definition",
            "function_declaration",
            "method_definition",
            "method_declaration",
            "constructor_declaration",
            "property_declaration",
            "function_item",     # Rust
            "primary_constructor",  # Kotlin
        ]:
            name = extract_name(node, source)
            symbols.append({
                "kind": "function",
                "name": name,
                "content": _decode_span(
                    source, node.start_byte, node.end_byte
                ),
                "start": node.start_byte,
                "end": node.end_byte,
                "calls": extract_calls_inside(node, source),
                "execution_flow": extract_execution_flow(node, source),
            })

        # Classes / Structs / Enums / Interfaces / Go types / Kotlin objects
        elif node.type in [
            "class_definition",
            "class_declaration",
            "class_specifier",         # C++
            "struct_specifier",        # C / C++ struct
            "union_specifier",         # C / C++ union
            "enum_specifier",          # C / C++ enum
            "struct_item",            # Rust
            "enum_item",              # Rust
            "trait_item",              # Rust
            "interface_declaration",   # TS / Java / Kotlin / C#
            "object_declaration",      # Kotlin
            "type_declaration",        # Go (struct/interface/alias)
            "type_spec",               # Go (inner type spec inside type_declaration)
            "record_declaration",      # Java records
        ]:
            kind = "class"
            if "struct" in node.type: kind = "struct"
            elif "union" in node.type: kind = "union"
            elif "enum" in node.type: kind = "enum"
            elif "trait" in node.type: kind = "trait"
            elif "interface" in node.type: kind = "interface"
            elif "object" in node.type: kind = "object"
            elif "record" in node.type: kind = "record"
            elif node.type in {"type_declaration", "type_spec"}: kind = "type"

            name = extract_name(node, source)
            symbols.append({
                "kind": kind,
                "name": name,
                "content": _decode_span(
                    source, node.start_byte, node.end_byte
                ),
                "start": node.start_byte,
                "end": node.end_byte,
                "calls": [],
                "execution_flow": [],
            })

        # Imports
        elif node.type in [
            "import_statement",       # Python
            "import_from_statement",  # Python
            "import_declaration",     # JS / TS / Java / Go
            "import_spec",            # Go (inner spec inside import_declaration)
            "use_declaration",        # Rust
            "import_header",          # Kotlin
            "using_directive",        # C#
        ]:
            import_names = extract_import_names(node, source)
            for name in import_names:
                imports.append(name)

        # Calls
        elif node.type in [
            "call",
            "call_expression",
            "invocation_expression",   # C#
            "method_invocation",        # Java
        ]:
            call_name = extract_call_name(node, source)
            if call_name and call_name not in {"if", "while", "for", "switch", "catch", "return", "def", "function", "class"}:
                calls.append(call_name)

        for child in node.children:
            walk(child)

    def extract_name(node, source):
        # Try direct identifier-like children first.
        for child in node.children:
            if child.type in [
                "identifier",
                "type_identifier",
                "field_identifier",
                "simple_identifier",   # Kotlin
                "property_identifier", # JS class properties
                "name",                # generic
            ]:
                return _decode_span(
                    source, child.start_byte, child.end_byte
                )
        # C / C++ wrap function names inside function_declarator (and may
        # nest further inside pointer_declarator/reference_declarator).
        for child in node.children:
            if child.type in {
                "function_declarator",
                "pointer_declarator",
                "reference_declarator",
                "init_declarator",
            }:
                inner = extract_name(child, source)
                if inner != "unknown":
                    return inner
        # Some grammars wrap the name in a `name` field (Java/Kotlin).
        try:
            name_node = node.child_by_field_name("name")
            if name_node:
                return _decode_span(
                    source, name_node.start_byte, name_node.end_byte
                )
        except Exception:
            pass
        # Go's type_declaration wraps a type_spec which holds the name.
        for child in node.children:
            if child.type == "type_spec":
                inner_name = extract_name(child, source)
                if inner_name != "unknown":
                    return inner_name
        return "unknown"

    def extract_import_names(node, source):
        names = []
        if node.type == "import_statement":
            # import os, sys -> ['os', 'sys']
            for child in node.children:
                if child.type == "dotted_name":
                    names.append(
                        _decode_span(
                            source, child.start_byte, child.end_byte
                        )
                    )
        elif node.type == "import_from_statement":
            # from pathlib import Path -> ['pathlib']
            for child in node.children:
                if child.type == "dotted_name":
                    names.append(
                        _decode_span(
                            source, child.start_byte, child.end_byte
                        )
                    )
                    break # Usually the first dotted_name is the module
        elif node.type == "import_declaration":
            # import { x } from 'y' -> ['y']
            for child in node.children:
                if child.type == "string":
                    names.append(
                        _decode_span(
                            source, child.start_byte, child.end_byte
                        ).strip("'\"")
                    )
        elif node.type == "use_declaration":
            # use std::collections::HashMap -> ['std::collections::HashMap']
            for child in node.children:
                if child.type in ["scoped_identifier", "identifier", "use_list"]:
                    names.append(
                        _decode_span(
                            source, child.start_byte, child.end_byte
                        )
                    )
        
        if not names:
            # Fallback
            names.append(
                _decode_span(source, node.start_byte, node.end_byte).strip()
            )
        return names

    def extract_call_name(node, source):
        if not node.children:
            return None
        func_node = node.children[0]
        if func_node.type == "identifier":
            return _decode_span(
                source, func_node.start_byte, func_node.end_byte
            )
        elif func_node.type in ["attribute", "member_expression", "member_access_expression"]:
            for child in reversed(func_node.children):
                if child.type in ["identifier", "property_identifier", "field_identifier"]:
                    return _decode_span(
                        source, child.start_byte, child.end_byte
                    )
        return None

    def extract_calls_inside(node, source):
        found = []

        def add_call(name):
            if name and name not in {
                "if", "while", "for", "switch", "catch", "return",
                "new", "public", "private", "protected", "internal",
                "void", "class"
            }:
                found.append(name)

        def walk_call(n):
            if n.type in ["call", "call_expression", "invocation_expression"]:
                call_name = extract_call_name(n, source)
                add_call(call_name)

            # fallback only for actual executable expression lines
            if n.type in ["expression_statement", "invocation_expression"]:
                text = _decode_span(
                    source, n.start_byte, n.end_byte
                ).strip()

                for m in re.finditer(r"\b\w+\.(\w+)\s*\(", text):
                    add_call(m.group(1))

                for m in re.finditer(r"(?<!\.)\b([A-Za-z_]\w*)\s*\(", text):
                    add_call(m.group(1))

            for child in n.children:
                walk_call(child)

        walk_call(node)
        return list(dict.fromkeys(found))

    walk(root)

    # Capture top-level flow (logic outside functions/classes)
    top_level_flow = extract_execution_flow(root, source)
    symbol_ranges = [(s["start"], s["end"]) for s in symbols]
    
    def is_outside(step):
        for start, end in symbol_ranges:
            if start <= step["start"] and step["end"] <= end:
                return False
        return True

    filtered_top_level = [step for step in top_level_flow if is_outside(step)]
    
    if filtered_top_level:
        symbols.append({
            "kind": "function", 
            "name": "<top-level>",
            "content": code,
            "start": 0,
            "end": len(source),
            "calls": calls,
            "execution_flow": filtered_top_level,
        })

    return {
        "symbols": symbols,
        "imports": list(set(imports)),
        "calls": list(set(calls))
    }


def structural_definitions(code: str, language: str) -> dict:
    """Additive view of :func:`parse_code_with_treesitter` for target grounding.

    ``parse_code_with_treesitter`` returns the same empty ``symbols`` list when
    a language has no parser and when a parsed file genuinely declares nothing,
    so a caller cannot tell "no structural proof is obtainable" from "the
    structural extractor says this definition does not exist".  That difference
    decides whether a short target spelling may be refused, so this wrapper
    reports it explicitly and adds the 1-based line range each definition spans.

    Parsing semantics are unchanged: the definitions are exactly the symbols the
    existing walker emits, with their existing kinds, names and byte spans.
    """
    lang_key = TREESITTER_LANG_MAP.get((language or "").lower())
    if not lang_key:
        return {"available": False, "definitions": []}

    try:
        from tree_sitter_language_pack import get_parser

        get_parser(lang_key)
    except Exception:
        return {"available": False, "definitions": []}

    parsed = parse_code_with_treesitter(code, language)

    # Every span tree-sitter reported indexes this buffer, the same one
    # ``parse_code_with_treesitter`` sliced, so line numbers derive from it.
    source = bytes(code, "utf8")
    definitions = []
    for symbol in parsed.get("symbols", []):
        name = symbol.get("name")
        if not name or name == "<top-level>":
            continue
        start = symbol.get("start") or 0
        end = symbol.get("end") or 0
        definitions.append({
            "kind": symbol.get("kind"),
            "name": name,
            "content": symbol.get("content", ""),
            "start": start,
            "end": end,
            "start_line": source.count(b"\n", 0, start) + 1,
            "end_line": source.count(b"\n", 0, end) + 1,
        })

    return {"available": True, "definitions": definitions}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: python treesitter_parse.py <language> <file_path>"}))
        sys.exit(1)

    lang = sys.argv[1]
    file_path = sys.argv[2]

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            code_content = f.read()
        
        parsed_results = parse_code_with_treesitter(code_content, lang)
        print(json.dumps(parsed_results, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
