from pathlib import Path
from datetime import datetime
import re

from graph.weights import is_noise_node, rank_nodes_by_weight

def make_obsidian_paths(base_path: str, snapshot: bool = False):
    base = Path(base_path)

    if snapshot:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return base / "snapshots" / ts

    return base / "latest"

def sanitize(name: str) -> str:
    name = str(name)
    name = name.replace("::", "__").replace("/", "_").replace("\\", "_")
    name = name.replace(":", "_")
    name = re.sub(r"[^\w\-. ]+", "_", name)
    return name[:120]


def export_graph_to_obsidian(
    graph,
    vault_path: str,
    include_noise: bool = False,
    repo_path: str | None = None,
):
    vault = Path(vault_path)
    vault.mkdir(parents=True, exist_ok=True)

    notes = {}

    for node_id, node in graph.nodes.items():
        if not include_noise and is_noise_node(node_id, node.type):
            continue

        notes[node_id] = {
            "label": node.label,
            "type": node.type,
            "contains": [],
            "contained_by": [],
            "imports": [],
            "imported_by": [],
            "calls": [],
            "called_by": [],
            "raw_calls": [],
            "executes": [],
        }

    for edge in graph.edges:
        src = edge.source
        dst = edge.target
        edge_type = edge.type

        if edge_type == "resolved_call":
            if src in notes and dst in notes:
                notes[src]["calls"].append(dst)
                notes[dst]["called_by"].append(src)

        elif edge_type == "calls":
            if include_noise and src in notes and dst in notes:
                notes[src]["raw_calls"].append(dst)

        elif edge_type == "contains":
            if src in notes and dst in notes:
                notes[src]["contains"].append(dst)
                notes[dst]["contained_by"].append(src)

        elif edge_type == "imports":
            if src in notes and dst in notes:
                notes[src]["imports"].append(dst)
                notes[dst]["imported_by"].append(src)

        elif edge_type == "executes":
            if include_noise and src in notes and dst in notes:
                notes[src]["executes"].append(dst)

    for node_id, info in notes.items():
        filepath = vault / f"{sanitize(node_id)}.md"

        tags = build_tags(info)
        hint = build_ai_hint(node_id, info)

        lines = [
            f"# {node_id}",
            "",
            f"Type: `{info['type']}`",
            f"Label: `{info['label']}`",
            f"Tags: {' '.join(tags) if tags else '#node'}",
            "",
            "## AI_HINT",
            hint,
            "",
        ]

        add_section(lines, "Contained By", info["contained_by"])
        add_section(lines, "Contains", info["contains"])
        add_section(lines, "Imports", info["imports"])
        add_section(lines, "Imported By", info["imported_by"])
        add_section(lines, "Calls", info["calls"])
        add_section(lines, "Called By", info["called_by"])

        filepath.write_text("\n".join(lines), encoding="utf-8")

    write_summary(vault, graph, notes, repo_path=repo_path)
    return str(vault)


def build_tags(info: dict) -> list[str]:
    tags = [f"#{info['type']}"]

    if info["called_by"]:
        tags.append("#called")
    if info["calls"]:
        tags.append("#caller")
    if info["type"] == "file":
        tags.append("#file")
    if info["type"] == "function":
        tags.append("#function")
    if info["type"] == "class":
        tags.append("#class")

    return tags


def build_ai_hint(node_id: str, info: dict) -> str:
    if info["type"] == "function":
        if info["called_by"] and not info["calls"]:
            return (
                "This is a leaf function in the resolved call graph. "
                "If a bug symptom matches this function name, inspect its implementation first."
            )
        if info["called_by"] and info["calls"]:
            return (
                "This function is in the middle of a call chain. "
                "Check both callers and callees before patching."
            )
        if info["calls"] and not info["called_by"]:
            return (
                "This function is a caller/entry-like function. "
                "If behavior starts here, trace its callees."
            )
        return "This function has no resolved call edges. Treat it as local or unresolved."

    if info["type"] == "file":
        return "This file groups symbols. Inspect contained functions/classes, not the file node alone."

    if info["type"] == "class":
        return "This class groups related functions/state. Inspect contained methods and their resolved calls."

    return "General graph node."


def add_section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        lines.append(f"## {title}")
        lines.append("none")
        lines.append("")
        return

    lines.append(f"## {title}")
    for item in sorted(set(items)):
        lines.append(f"- [[{sanitize(item)}]]")
    lines.append("")


def write_summary(
    vault: Path,
    graph,
    notes: dict,
    repo_path: str | None = None,
) -> None:
    important = []

    for metric in rank_nodes_by_weight(graph, limit=len(graph.nodes), repo_path=repo_path):
        info = notes.get(metric.node_id)
        if info is not None and metric.weight > 0:
            important.append((metric.weight, metric.node_id, info))

    lines = [
        "# GRAPH SUMMARY",
        "",
        f"- Time Stamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Total raw nodes: {len(graph.nodes)}",
        f"- Total raw edges: {len(graph.edges)}",
        f"- Exported semantic notes: {len(notes)}",
        "",
        "## AI_READ_FIRST",
        "Read these notes first when analyzing this project:",
        "",
    ]

    for score, node_id, info in important[:10]:
        lines.append(f"- [[{sanitize(node_id)}]] score={score:.2f} type={info['type']}")

    lines.append("")
    lines.append("## Rule for small models")
    lines.append("- Start from AI_READ_FIRST.")
    lines.append("- Prefer `resolved_call` relationships over raw `call::` nodes.")
    lines.append("- Ignore expression nodes unless debugging exact execution state.")

    (vault / "GRAPH_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
