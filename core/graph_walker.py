from graph.query import explain_symbol
from graph.obsidian_exporter import export_graph_to_obsidian
from core.semantic_graph_pipeline import extract_ai_read_first, get_semantic_graph
from pathlib import Path

def walk_from_nodes(graph, start_nodes: list[str], max_depth=2):
    visited = set()
    paths = []

    def dfs(node, path, depth):
        if depth > max_depth or node in visited:
            return

        visited.add(node)
        path.append(node)

        info = explain_symbol(graph, node)

        # 🔥 backward (caller)
        for caller in info.get("called_by", [])[:2]:
            dfs(caller, path.copy(), depth + 1)

        # 🔥 forward (callee)
        for callee in info.get("calls", [])[:2]:
            dfs(callee, path.copy(), depth + 1)

        paths.append(path)

    for n in start_nodes:
        dfs(n, [], 0)

    return paths

def get_ai_top_nodes(repo_path: str, vault_path: str, top_k: int = 3) -> list[str]:
    graph = get_semantic_graph(repo_path)
    export_graph_to_obsidian(graph, vault_path)

    summary_path = Path(vault_path) / "GRAPH_SUMMARY.md"
    if not summary_path.exists():
        return []

    summary = summary_path.read_text(encoding="utf-8", errors="replace")
    return extract_ai_read_first(summary, top_k=top_k)