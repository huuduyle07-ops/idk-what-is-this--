from collections import defaultdict
from pathlib import Path


def module_of(node_id: str) -> str:
    # file node: core/retriever.py
    if "::" not in node_id:
        return str(Path(node_id).parent).replace("\\", "/") or "root"

    # symbol node: core/retriever.py::retrieve_context
    file_part = node_id.split("::")[0]
    return str(Path(file_part).parent).replace("\\", "/") or "root"


def compress_to_modules(graph):
    modules = defaultdict(lambda: {
        "nodes": set(),
        "edges": defaultdict(int),
    })

    node_to_module = {}

    for node_id in graph.nodes:
        m = module_of(node_id)
        node_to_module[node_id] = m
        modules[m]["nodes"].add(node_id)

    for edge in graph.edges:
        src_m = node_to_module.get(edge.source)
        dst_m = node_to_module.get(edge.target)

        if not src_m or not dst_m or src_m == dst_m:
            continue

        key = (src_m, dst_m, edge.type)
        modules[src_m]["edges"][key] += 1

    return {
        "modules": {
            m: {
                "node_count": len(data["nodes"]),
                "nodes": sorted(data["nodes"])[:20],
            }
            for m, data in modules.items()
        },
        "edges": [
            {
                "source": src,
                "target": dst,
                "type": typ,
                "weight": weight,
            }
            for m, data in modules.items()
            for (src, dst, typ), weight in data["edges"].items()
        ]
    }