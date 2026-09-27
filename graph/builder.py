import re
from pathlib import Path
from typing import TYPE_CHECKING

from config import LANGUAGE_MAP, SUPPORTED_EXTENSIONS
from core.dependency_target import (
    resolve_dependency_target,
)
from core.repo_librarian import iter_repo_files
from core.repository_inventory import (
    CANONICAL_WALK_SITE,
    repository_inventory_from_entries,
    validate_repository_inventory,
)
from core.treesitter_parse import parse_code_with_treesitter
from graph.schema import ProgramGraph

if TYPE_CHECKING:
    from core.repository_inventory import RepositoryInventory


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

def build_graph_from_repo(
    repo_path: str,
    *,
    inventory: "RepositoryInventory | None" = None,
    repo_entries=None,
    repository_files=None,
) -> ProgramGraph:
    graph = ProgramGraph()
    root = Path(repo_path).resolve()
    if inventory is not None and repo_entries is not None:
        raise ValueError(
            "supply inventory or repo_entries, not both"
        )

    if inventory is not None:
        operation_inventory = validate_repository_inventory(
            root,
            inventory,
        )
    else:
        supplied_entries = repo_entries is not None
        entries = tuple(
            repo_entries
            if supplied_entries
            else iter_repo_files(str(root))
        )
        operation_inventory = repository_inventory_from_entries(
            root,
            entries,
            traversal_count=0 if supplied_entries else 1,
            walk_sites=(
                ()
                if supplied_entries
                else (CANONICAL_WALK_SITE,)
            ),
            sort_entries=not supplied_entries,
        )

    entries = operation_inventory.indexable_entry_pairs
    expected_files = set(
        operation_inventory.relative_paths(None)
    )
    if repository_files is None:
        files = expected_files
    else:
        files = {
            str(path).replace("\\", "/")
            for path in repository_files
        }
        if files != expected_files:
            raise ValueError(
                "repository_files does not match supplied repository "
                "inventory"
            )

    for path, rel_path in entries:
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
        # Recorded while the file is already open, so RETRIEVE.LIVE.1's span
        # consistency check costs no read and no second traversal.  Assigned
        # after add_node because an earlier file's import may already have
        # created this node, and add_node leaves an existing node alone.
        # The length is of the re-encoded text, which is exactly the buffer
        # the parser reported its offsets against.
        file_metadata = graph.nodes[rel].metadata
        file_metadata["language"] = language
        file_metadata["source_bytes"] = len(text.encode("utf-8"))

        for imp in imports:
            target = resolve_dependency_target(
                repo_root=root,
                source_file=rel,
                language=language,
                raw_target=imp,
                repository_files=files,
            )
            if target.target_file:
                graph.add_node(
                    target.target_file,
                    "file",
                    target.target_file,
                )
                graph.add_edge(
                    rel,
                    target.target_file,
                    "imports",
                )

        for sym in symbols:
            name = sym.get("name")
            if not name or name == "unknown":
                continue

            sym_id = f"{rel}::{name}"
            graph.add_node(
                sym_id,
                sym.get("kind", "symbol"),
                name,
                file=rel,
                language=language,
                # Byte offsets into the UTF-8 buffer the parser read, the same
                # contract patching/patch_engine.py already slices with.
                start=sym.get("start"),
                end=sym.get("end"),
            )
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

        # removeprefix, not replace: a call name that itself contains the
        # marker must not be mangled on its way to the symbol table.
        call_name = edge.target.removeprefix("call::")
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
