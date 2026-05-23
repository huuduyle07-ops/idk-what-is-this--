import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.project_map import compute_symbol_hotspots
from graph.schema import ProgramGraph


def test_compute_symbol_hotspots_uses_universal_weights_for_tied_in_degree():
    graph = ProgramGraph()
    graph.add_node("app.py::start", "function")
    graph.add_node("app.py::a_low", "function")
    graph.add_node("app.py::z_high", "function")
    graph.add_node("app.py::down1", "function")
    graph.add_node("app.py::down2", "function")
    graph.add_node("app.py::z_high::expr::1", "expression")

    graph.add_edge("app.py::start", "app.py::z_high", "resolved_call")
    graph.add_edge("app.py::start", "app.py::a_low", "resolved_call")
    graph.add_edge("app.py::z_high", "app.py::down1", "resolved_call")
    graph.add_edge("app.py::z_high", "app.py::down2", "resolved_call")
    graph.add_edge("app.py::z_high", "app.py::z_high::expr::1", "executes")

    ranked = compute_symbol_hotspots(graph)

    assert ranked[0][0] == "app.py::z_high"
    assert all(isinstance(item, tuple) for item in ranked)


def test_compute_symbol_hotspots_only_ranks_semantic_symbols():
    graph = ProgramGraph()
    graph.add_node("app.py", "file")
    graph.add_node("app.py::Widget", "class")
    graph.add_node("app.py::render", "function")
    graph.add_node("app.py::render::expr::1", "expression")
    graph.add_node("call::render", "call")

    graph.add_edge("app.py", "app.py::Widget", "contains")
    graph.add_edge("app.py::Widget", "app.py::render", "contains")
    graph.add_edge("app.py::render", "app.py::render::expr::1", "executes")
    graph.add_edge("app.py::render", "call::render", "calls")

    ranked = compute_symbol_hotspots(graph)
    node_ids = [node_id for node_id, _ in ranked]

    assert "app.py::Widget" in node_ids
    assert "app.py::render" in node_ids
    assert "app.py" not in node_ids
    assert "app.py::render::expr::1" not in node_ids
    assert "call::render" not in node_ids


def test_compute_symbol_hotspots_includes_union_symbols():
    graph = ProgramGraph()
    graph.add_node("types.py::Result", "union")
    graph.add_node("types.py::Ok", "type")
    graph.add_edge("types.py::Result", "types.py::Ok", "contains")

    ranked = compute_symbol_hotspots(graph)
    node_ids = [node_id for node_id, _ in ranked]

    assert "types.py::Result" in node_ids
