import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.penalty import PenaltyResult
from graph.schema import ProgramGraph
from graph.weights import (
    compute_node_weights,
    get_node_weight,
    is_noise_node,
    rank_nodes_by_weight,
)


def build_weighted_graph() -> ProgramGraph:
    graph = ProgramGraph()
    graph.add_node("core/a.py", "file")
    graph.add_node("core/b.py", "file")
    graph.add_node("core/c.py", "file")
    graph.add_node("core/a.py::main", "function")
    graph.add_node("core/b.py::helper", "function")
    graph.add_node("core/c.py::utility", "function")
    graph.add_node("core/a.py::Runner", "class")
    graph.add_node("core/a.py::Runner::run", "function")
    graph.add_node("call::helper", "call")
    graph.add_node("core/a.py::main::expr::1", "expression")

    graph.add_edge("core/a.py", "core/b.py", "imports")
    graph.add_edge("core/a.py", "core/a.py::main", "contains")
    graph.add_edge("core/b.py", "core/b.py::helper", "contains")
    graph.add_edge("core/c.py", "core/c.py::utility", "contains")
    graph.add_edge("core/a.py", "core/a.py::Runner", "contains")
    graph.add_edge("core/a.py::Runner", "core/a.py::Runner::run", "contains")
    graph.add_edge("core/a.py::main", "core/b.py::helper", "resolved_call")
    graph.add_edge("core/c.py::utility", "core/b.py::helper", "resolved_call")
    graph.add_edge("core/a.py::main", "core/c.py::utility", "resolved_call")
    graph.add_edge("core/a.py::main", "core/a.py::main::expr::1", "executes")
    graph.add_edge("core/a.py::main", "call::helper", "calls")
    graph.add_edge("core/a.py::main", "core/b.py", "unexpected")
    return graph


def test_compute_node_weights_excludes_noise_by_default():
    graph = build_weighted_graph()

    metrics = compute_node_weights(graph)

    assert "call::helper" not in metrics
    assert "core/a.py::main::expr::1" not in metrics
    assert metrics["core/b.py::helper"].in_degree == 2
    assert metrics["core/a.py::main"].out_degree == 2
    assert metrics["core/a.py::main"].complexity == 1
    assert metrics["core/a.py::Runner"].out_degree == 1
    assert metrics["core/a.py::Runner"].complexity == 1
    assert metrics["core/b.py::helper"].weight > metrics["core/a.py::main"].weight
    assert "in_degree=2" in metrics["core/b.py::helper"].reasons
    assert "unexpected" not in metrics["core/b.py"].reasons


def test_resolved_call_to_class_counts_as_incoming_reference():
    graph = ProgramGraph()
    graph.add_node("core/a.py::main", "function")
    graph.add_node("core/a.py::Runner", "class")

    graph.add_edge("core/a.py::main", "core/a.py::Runner", "resolved_call")

    metrics = compute_node_weights(graph)

    assert metrics["core/a.py::Runner"].in_degree == 1
    assert metrics["core/a.py::Runner"].weight > 0
    assert "in_degree=1" in metrics["core/a.py::Runner"].reasons


def test_union_nodes_use_type_node_contains_metrics():
    graph = ProgramGraph()
    graph.add_node("types.py::Result", "union")
    graph.add_node("types.py::Ok", "type")
    graph.add_node("types.py::Err", "type")

    graph.add_edge("types.py::Result", "types.py::Ok", "contains")
    graph.add_edge("types.py::Result", "types.py::Err", "contains")

    metrics = compute_node_weights(graph)

    assert metrics["types.py::Result"].out_degree == 2
    assert metrics["types.py::Result"].complexity == 2
    assert "out_degree=2" in metrics["types.py::Result"].reasons
    assert "complexity=2" in metrics["types.py::Result"].reasons


def test_compute_node_weights_can_include_noise_nodes():
    graph = build_weighted_graph()

    metrics = compute_node_weights(graph, include_noise=True)

    assert "call::helper" in metrics
    assert "core/a.py::main::expr::1" in metrics
    assert is_noise_node("call::helper", "symbol")
    assert is_noise_node("module.py::expr::1", "symbol")
    assert is_noise_node("not_prefixed", "expression")


def test_get_node_weight_defaults_missing_nodes_to_zero():
    metrics = compute_node_weights(ProgramGraph())

    assert metrics == {}
    assert get_node_weight(metrics, "missing") == 0.0


def test_rank_nodes_by_weight_orders_highest_weight_first():
    graph = build_weighted_graph()

    ranked = rank_nodes_by_weight(graph, limit=3, node_types={"function"})

    assert [item.node_id for item in ranked] == [
        "core/b.py::helper",
        "core/c.py::utility",
        "core/a.py::main",
    ]


def test_repo_path_threads_penalty_into_weight_field_and_reasons(tmp_path):
    graph = ProgramGraph()
    graph.add_node("foo.py", "file")
    graph.add_node("bar.py", "file")
    graph.add_edge("foo.py", "bar.py", "imports")

    fake = PenaltyResult(
        penalty_map={"foo.py": 7.0},
        unmatched_paths=[],
        blocked_counts={"foo.py": 1},
        transient_counts={"foo.py": 2},
    )

    structural = compute_node_weights(graph)
    with patch("graph.weights.build_penalty_map", return_value=fake):
        penalized = compute_node_weights(graph, repo_path=str(tmp_path))

    assert penalized["foo.py"].penalty == 7.0
    assert penalized["foo.py"].weight == structural["foo.py"].weight + 7.0
    assert "blocked_lessons=1" in penalized["foo.py"].reasons
    assert "patch_failures=2" in penalized["foo.py"].reasons

    # bar.py has no penalty contribution — clean
    assert penalized["bar.py"].penalty == 0.0
    assert penalized["bar.py"].weight == structural["bar.py"].weight
    assert not any(r.startswith("blocked_lessons") for r in penalized["bar.py"].reasons)
    assert not any(r.startswith("patch_failures") for r in penalized["bar.py"].reasons)


def test_repo_path_none_keeps_v1_structural_only_behavior():
    graph = build_weighted_graph()

    baseline = compute_node_weights(graph)
    with patch("graph.weights.build_penalty_map") as mock_build:
        result = compute_node_weights(graph, repo_path=None)

    assert result == baseline
    mock_build.assert_not_called()
    for metric in result.values():
        assert metric.penalty == 0.0
