from pathlib import Path

from graph.builder import build_graph_from_repo
from graph.obsidian_exporter import export_graph_to_obsidian


_graph_cache = {}


def get_semantic_graph(repo_path: str):
    repo = str(Path(repo_path).resolve())

    if repo not in _graph_cache:
        _graph_cache[repo] = build_graph_from_repo(repo)

    return _graph_cache[repo]


def build_obsidian_semantic_context(
    repo_path: str,
    vault_path: str,
    max_chars: int = 4000,
) -> str:
    graph = get_semantic_graph(repo_path)

    export_graph_to_obsidian(graph, vault_path, repo_path=repo_path)

    summary_path = Path(vault_path) / "GRAPH_SUMMARY.md"

    if not summary_path.exists():
        return ""

    summary = summary_path.read_text(encoding="utf-8", errors="replace")
    important_nodes = extract_ai_read_first(summary)

    return f"""
=== SEMANTIC GRAPH / OBSIDIAN CONTEXT ===

AI_TOP_NODES:
{important_nodes}

INSTRUCTION:
Start from AI_TOP_NODES.
Trace resolved_call relationships.
Do NOT scan entire project blindly.

{summary[:max_chars]}
""".strip()

def extract_ai_read_first(summary: str, top_k: int = 3) -> list[str]:
    lines = summary.splitlines()

    result = []
    capture = False

    for line in lines:
        if "AI_READ_FIRST" in line:
            capture = True
            continue

        if capture:
            if line.strip().startswith("- [["):
                # extract node name
                node = line.split("[[")[1].split("]]")[0]
                node = node.replace("__", "::")
                result.append(node)
            elif line.strip() == "":
                break

    return result[:top_k]