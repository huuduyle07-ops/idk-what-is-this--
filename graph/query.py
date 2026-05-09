def find_callers(graph, target_name: str):
    result = []
    for edge in graph.edges:
        if edge.type != "resolved_call":
            continue
        if target_name.lower() in edge.target.lower():
            result.append(edge.source)
    return result

def find_callees(graph, source_name: str):
    result = []
    for edge in graph.edges:
        if edge.type != "resolved_call":
            continue
        if edge.source.endswith(f"::{source_name}"):
            result.append(edge.target)
    return result

def explain_symbol(graph, symbol_name: str):
    callers = find_callers(graph, symbol_name)
    callees = find_callees(graph, symbol_name)

    return {
        "symbol": symbol_name,
        "called_by": callers,
        "calls": callees,
    }

def impact_analysis(graph, symbol_name: str):
    affected = set()

    for edge in graph.edges:
        if edge.type != "resolved_call":
            continue

        if edge.target.endswith(f"::{symbol_name}"):
            affected.add(edge.source)

    return list(affected)

def trace_path(graph, start: str, end: str, max_depth=5):
    paths = []

    def dfs(current, path, depth):
        if depth > max_depth:
            return
        if current.endswith(f"::{end}"):
            paths.append(path[:])
            return

        for edge in graph.edges:
            if edge.type != "resolved_call":
                continue
            if edge.source == current:
                dfs(edge.target, path + [edge.target], depth + 1)

    for node in graph.nodes:
        if node.endswith(f"::{start}"):
            dfs(node, [node], 0)

    return paths