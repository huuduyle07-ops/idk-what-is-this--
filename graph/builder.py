from pathlib import Path
from config import LANGUAGE_MAP, SUPPORTED_EXTENSIONS
from core.treesitter_parse import parse_code_with_treesitter
from graph.schema import ProgramGraph
from core.repo_librarian import iter_repo_files
import re

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".vscode",
    ".idea",
    ".agent",
    "Obsidian Graph",
    "obsidian_graph",
    "test",
    ".env",
    "storage",
    ".claude"
}

def build_graph_from_repo(repo_path: str) -> ProgramGraph:
    graph = ProgramGraph()
    root = Path(repo_path).resolve()

    for path, rel_path in iter_repo_files(repo_path):
        rel = str(rel_path).replace("\\", "/")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        language = LANGUAGE_MAP.get(ext)
        if not language:
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_code_with_treesitter(text, language)

        imports = parsed.get("imports", [])
        symbols = parsed.get("symbols", [])

        if not symbols and language == "csharp":
            symbols = fallback_csharp_symbols(text)

        graph.add_node(rel, "file", rel)

        for imp in imports:
            target_file = resolve_import_to_file(imp, root, rel)
            if target_file:
                graph.add_node(target_file, "file", target_file)
                graph.add_edge(rel, target_file, "imports")

        for sym in symbols:
            name = sym.get("name")
            if not name or name == "unknown":
                continue

            sym_id = f"{rel}::{name}"
            graph.add_node(sym_id, sym.get("kind", "symbol"), name)
            graph.add_edge(rel, sym_id, "contains")

            for step in sym.get("execution_flow", []):
                if step.get("type") == "expression":
                    node_id = f"{sym_id}::expr::{step.get('start')}"
                    graph.add_node(node_id, "expression", step.get("text", ""))
                    graph.add_edge(sym_id, node_id, "executes")

            if sym.get("kind") == "function":
                for call in sym.get("calls", []):
                    call_id = f"call::{call}"
                    graph.add_node(call_id, "call", call)
                    graph.add_edge(sym_id, call_id, "calls")

    graph = resolve_call_edges(graph)
    return graph

def resolve_import_to_file(import_name: str, root: Path, current_rel: str | None = None):
    name = (import_name or "").strip()
    if not name:
        return None

    # Tree-sitter usually returns module paths; handle simple fallback forms safely.
    if name.startswith("from ") and " import " in name:
        name = name[5:name.index(" import ")].strip()
    elif name.startswith("import "):
        # Keep the first import target only (e.g., "import os, sys").
        name = name[7:].split(",")[0].strip()

    def first_existing(candidates: list[Path]) -> str | None:
        for candidate in candidates:
            if candidate.exists():
                return str(candidate.relative_to(root))
        return None

    # Relative imports: .foo, ..pkg.mod
    if name.startswith("."):
        if not current_rel:
            return None

        current_dir = Path(current_rel).parent
        dot_count = len(name) - len(name.lstrip("."))
        suffix = name[dot_count:]

        anchor = current_dir
        for _ in range(max(dot_count - 1, 0)):
            anchor = anchor.parent

        if suffix:
            rel_mod = suffix.replace(".", "/")
            resolved = first_existing([
                root / anchor / f"{rel_mod}.py",
                root / anchor / rel_mod / "__init__.py",
            ])
            if resolved:
                return resolved

        # `from . import x` often identifies the package itself.
        resolved = first_existing([root / anchor / "__init__.py"])
        if resolved:
            return resolved
        return None

    rel_mod = name.replace(".", "/")
    return first_existing([
        root / f"{rel_mod}.py",
        root / rel_mod / "__init__.py",
    ])

def fallback_csharp_symbols(text: str):
    symbols = []

    for m in re.finditer(r"\bclass\s+(\w+)", text):
        symbols.append({
            "kind": "class",
            "name": m.group(1),
            "calls": [],
        })

    for m in re.finditer(r"\b(?:public|private|protected|internal|static|void|int|float|string|bool|\w+)\s+(\w+)\s*\(", text):
        name = m.group(1)
        if name not in {"if", "for", "while", "switch", "catch"}:
            symbols.append({
                "kind": "function",
                "name": name,
                "calls": [],
            })

    return symbols

def resolve_call_edges(graph):
    symbol_by_name = {}

    for node_id, node in graph.nodes.items():
        if "::" in node_id and not node_id.startswith("call::"):
            name = node_id.split("::")[-1]
            symbol_by_name.setdefault(name, []).append(node_id)

    resolved_edges = []
    existing_resolved = {
        (edge.source, edge.target, edge.type)
        for edge in graph.edges
        if edge.type == "resolved_call"
    }

    for edge in list(graph.edges):

        if not edge.target.startswith("call::"):
            continue

        call_name = edge.target.replace("call::", "")
        targets = symbol_by_name.get(call_name, [])

        for real_target in targets:
            if real_target != edge.source:
                key = (edge.source, real_target, "resolved_call")
                if key in existing_resolved:
                    continue
                existing_resolved.add(key)
                resolved_edges.append((edge.source, real_target))

    for source, target in resolved_edges:
        graph.add_edge(source, target, "resolved_call")

    return graph
