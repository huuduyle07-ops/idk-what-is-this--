import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import control_engine
from graph import weights as weights_module
from graph.penalty import PenaltyResult
from graph.schema import ProgramGraph
from graph.weights import NodeWeight


def _stub_explain_helpers(monkeypatch, calls_map):
    def explain(graph, symbol):
        return {"symbol": symbol, "called_by": [], "calls": calls_map.get(symbol, [])}
    monkeypatch.setattr(control_engine, "explain_symbol", explain)
    monkeypatch.setattr(control_engine, "impact_analysis", lambda graph, symbol: [])
    monkeypatch.setattr(
        control_engine,
        "analyze_symbol_risk",
        lambda graph, symbol: {"risk_level": "low", "risk_score": 0},
    )


def _metric(node_id: str, weight: float) -> NodeWeight:
    return NodeWeight(
        node_id=node_id,
        node_type="function",
        weight=weight,
    )


def test_control_dfs_evidence_includes_graph_weight(monkeypatch):
    graph = ProgramGraph()
    graph.add_node("app.py::start", "function")
    metrics = {"app.py::start": _metric("app.py::start", 2.25)}

    monkeypatch.setattr(
        control_engine,
        "explain_symbol",
        lambda graph, symbol: {"symbol": symbol, "called_by": [], "calls": []},
    )
    monkeypatch.setattr(control_engine, "impact_analysis", lambda graph, symbol: [])
    monkeypatch.setattr(
        control_engine,
        "analyze_symbol_risk",
        lambda graph, symbol: {"risk_level": "low", "risk_score": 0},
    )

    evidence = control_engine.control_dfs_v2(
        graph,
        ["app.py::start"],
        node_metrics=metrics,
    )

    assert evidence[0]["graph_weight"] == 2.25


def test_score_control_node_uses_graph_weight():
    without_weight = control_engine.score_control_node({
        "risk": {"risk_level": "low", "risk_score": 0},
        "called_by": [],
        "calls": [],
        "impact": [],
        "query_bonus": 0,
        "depth": 0,
    })
    with_weight = control_engine.score_control_node({
        "risk": {"risk_level": "low", "risk_score": 0},
        "called_by": [],
        "calls": [],
        "impact": [],
        "query_bonus": 0,
        "depth": 0,
        "graph_weight": 3.5,
    })

    assert with_weight == without_weight + 3.5


def test_control_dfs_prioritizes_graph_weight_when_query_relevance_is_tied(monkeypatch):
    graph = ProgramGraph()
    graph.add_node("app.py::start", "function")
    graph.add_node("app.py::a_low", "function")
    graph.add_node("app.py::z_high", "function")
    graph.add_node("app.py::z_helper_one", "function")
    graph.add_node("app.py::z_helper_two", "function")
    graph.add_node("app.py::z_high::expr::1", "expression")
    graph.add_edge("app.py::start", "app.py::a_low", "resolved_call")
    graph.add_edge("app.py::start", "app.py::z_high", "resolved_call")
    graph.add_edge("app.py::z_high", "app.py::z_helper_one", "resolved_call")
    graph.add_edge("app.py::z_high", "app.py::z_helper_two", "resolved_call")
    graph.add_edge("app.py::z_high", "app.py::z_high::expr::1", "executes")

    def explain_symbol(graph, symbol):
        if symbol == "app.py::start":
            return {
                "symbol": symbol,
                "called_by": [],
                "calls": ["app.py::z_high", "app.py::a_low"],
            }
        return {"symbol": symbol, "called_by": [], "calls": []}

    monkeypatch.setattr(control_engine, "explain_symbol", explain_symbol)
    monkeypatch.setattr(control_engine, "impact_analysis", lambda graph, symbol: [])
    monkeypatch.setattr(
        control_engine,
        "analyze_symbol_risk",
        lambda graph, symbol: {"risk_level": "low", "risk_score": 0},
    )

    evidence = control_engine.control_dfs_v2(
        graph,
        ["app.py::start"],
        query="unmatched term",
        max_depth=2,
        max_nodes=10,
        neighbor_limit=1,
    )

    symbols = {item["symbol"] for item in evidence}
    assert "app.py::z_high" in symbols
    assert "app.py::a_low" not in symbols


def test_control_dfs_visits_high_penalty_neighbor_first(monkeypatch, tmp_path):
    """Neighbour ordering follows the penalty-boosted weight.

    The neighbours are symbols rather than bare file nodes because RETRIEVE.
    LIVE.1 refuses a structural node as a localization candidate, and because
    that is the shape production actually produces: ``resolved_call`` edges
    are built from the symbol table and never target a file node.  What this
    test pins - that the higher-penalty neighbour is the one visited under a
    neighbour limit of one, and that the penalty reaches the evidence row - is
    unchanged.
    """
    graph = ProgramGraph()
    graph.add_node("entry.py::start", "function")
    graph.add_node("low.py::run", "function")
    graph.add_node("high.py::run", "function")
    graph.add_edge("entry.py::start", "low.py::run", "resolved_call")
    graph.add_edge("entry.py::start", "high.py::run", "resolved_call")

    fake = PenaltyResult(
        penalty_map={"high.py::run": 10.0},
        unmatched_paths=[],
        blocked_counts={"high.py::run": 2},
        transient_counts={},
    )
    monkeypatch.setattr(weights_module, "build_penalty_map", lambda g, rp: fake)
    _stub_explain_helpers(monkeypatch, {
        "entry.py::start": ["high.py::run", "low.py::run"],
    })

    evidence = control_engine.control_dfs_v2(
        graph,
        ["entry.py::start"],
        repo_path=str(tmp_path),
        neighbor_limit=1,
    )

    symbols = {item["symbol"] for item in evidence}
    assert "high.py::run" in symbols
    assert "low.py::run" not in symbols
    high_row = next(item for item in evidence if item["symbol"] == "high.py::run")
    assert high_row["graph_weight"] >= 10.0  # penalty boost is in evidence


def test_control_dfs_visits_high_penalty_symbol_over_tied_sibling(monkeypatch, tmp_path):
    graph = ProgramGraph()
    graph.add_node("entry.py::start", "function")
    graph.add_node("mod.py::quiet_func", "function")
    graph.add_node("mod.py::risky_func", "function")
    graph.add_edge("entry.py::start", "mod.py::quiet_func", "resolved_call")
    graph.add_edge("entry.py::start", "mod.py::risky_func", "resolved_call")

    fake = PenaltyResult(
        penalty_map={"mod.py::risky_func": 4.0},
        unmatched_paths=[],
        blocked_counts={},
        transient_counts={"mod.py::risky_func": 4},
    )
    monkeypatch.setattr(weights_module, "build_penalty_map", lambda g, rp: fake)
    _stub_explain_helpers(monkeypatch, {
        "entry.py::start": ["mod.py::quiet_func", "mod.py::risky_func"],
    })

    evidence = control_engine.control_dfs_v2(
        graph,
        ["entry.py::start"],
        repo_path=str(tmp_path),
        neighbor_limit=1,
    )

    symbols = {item["symbol"] for item in evidence}
    assert "mod.py::risky_func" in symbols
    assert "mod.py::quiet_func" not in symbols


def test_format_control_context_prints_graph_weight():
    context = control_engine.format_control_context({
        "query": "why",
        "repo_path": ".",
        "entry_nodes": [],
        "top_hypothesis": None,
        "hypotheses": [],
        "evidence": [
            {
                "symbol": "app.py::start",
                "depth": 0,
                "score": 7.0,
                "graph_weight": 2.5,
                "risk": {"risk_level": "low", "risk_score": 1},
                "called_by": [],
                "calls": [],
                "impact": [],
            }
        ],
        "execution_trace": "",
        "phantom_limb": {},
        "control_rules": [],
    })

    assert "- score: 7.00\n- graph_weight: 2.50\n- risk: low (1)" in context
