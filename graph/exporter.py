from __future__ import annotations
import hashlib
import json
import re
from graph.schema import ProgramGraph


def export_json(graph: ProgramGraph, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(graph.to_dict(), f, indent=2, ensure_ascii=False)

def escape_mermaid_label(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "'")
    )

def export_mermaid(graph: ProgramGraph) -> str:
    lines = ["graph TD"]

    for edge in graph.edges:
        src = safe_id(edge.source)
        tgt = safe_id(edge.target)
        label = escape_mermaid_label(edge.type)
        src_label = escape_mermaid_label(edge.source)
        tgt_label = escape_mermaid_label(edge.target)

        lines.append(
            f'  {src}["{src_label}"] -->|{label}| {tgt}["{tgt_label}"]'
        )

    return "\n".join(lines)


def safe_id(text: str) -> str:
    """Mermaid-safe identifier for a node.

    Strategy:
      1. Replace every non-[A-Za-z0-9_] char with '_' (Mermaid grammar requires this).
      2. Prepend 'node_' if the result starts with a digit or is empty.
      3. Append a short stable hash of the ORIGINAL text so two distinct names
         that sanitize to the same form still get distinct IDs.

    Example collision the hash prevents:
      safe_id("a-b") -> "a_b_2c2dba"
      safe_id("a/b") -> "a_b_43839c"
      (without the hash, both became "a_b" — Mermaid would merge them.)

    The hash is deterministic, so the same input always yields the same ID
    across runs — safe to embed in cached/exported Mermaid sources.
    """
    text_str = str(text)
    safe = re.sub(r"[^A-Za-z0-9_]", "_", text_str)

    if not safe:
        safe = "node_empty"
    elif safe[0].isdigit():
        safe = "node_" + safe

    short_hash = hashlib.sha1(text_str.encode("utf-8", errors="replace")).hexdigest()[:6]
    return f"{safe}_{short_hash}"