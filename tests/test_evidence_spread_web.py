from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.schema import ProgramGraph, build_graph
from graph.weights import compute_node_weights


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _target_graph() -> ProgramGraph:
    return build_graph(
        [
            {"id": "target.py", "type": "file", "label": "target.py"},
            {"id": "target.py::fib", "type": "function", "label": "fib"},
            {"id": "target.py::helper", "type": "function", "label": "helper"},
            {"id": "tests/test_target.py", "type": "file", "label": "test_target.py"},
            {
                "id": "tests/test_target.py::test_fib",
                "type": "function",
                "label": "test_fib",
            },
        ],
        [
            {"source": "target.py", "target": "target.py::fib", "type": "contains"},
            {"source": "target.py", "target": "target.py::helper", "type": "contains"},
            {
                "source": "target.py::fib",
                "target": "target.py::helper",
                "type": "calls",
            },
            {
                "source": "tests/test_target.py",
                "target": "tests/test_target.py::test_fib",
                "type": "contains",
            },
            {
                "source": "tests/test_target.py::test_fib",
                "target": "target.py::fib",
                "type": "calls",
            },
        ],
    )


def test_graph_evidence_spread_route_returns_explanations(tmp_path, monkeypatch):
    from web import app as web_app

    graph = _target_graph()
    monkeypatch.setattr(web_app, "build_graph_from_repo", lambda repo_path: graph)
    monkeypatch.setattr(
        web_app,
        "run_gemini_request",
        lambda prompt: (_ for _ in ()).throw(AssertionError("model call not allowed")),
    )

    with web_app.app.test_client() as client:
        response = client.post(
            "/graph/evidence_spread",
            data={
                "repo_path": str(_repo(tmp_path)),
                "query": "optimize fib",
                "target_node": "target.py::fib",
                "top_n": "4",
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["empty"] is False
    assert data["query"] == "optimize fib"
    assert data["target_node"] == "target.py::fib"

    top = data["nodes"][0]
    assert top["node_id"] == "target.py::fib"
    assert set(top) >= {"final_score", "base_score", "spread_score", "reasons"}
    assert any("query" in reason.lower() for reason in top["reasons"])

    assert data["scope_assessment"]["scope"] == "api_contract_risk"
    assert "tests/test_target.py::test_fib" in data["scope_assessment"]["evidence_nodes"]


def test_graph_evidence_spread_route_empty_graph_or_query_is_friendly(
    tmp_path, monkeypatch
):
    from web import app as web_app

    monkeypatch.setattr(web_app, "build_graph_from_repo", lambda repo_path: ProgramGraph())

    with web_app.app.test_client() as client:
        response = client.post(
            "/graph/evidence_spread",
            data={"repo_path": str(_repo(tmp_path)), "query": "", "top_n": "5"},
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["empty"] is True
    assert data["nodes"] == []
    assert "No graph evidence" in data["message"]


def test_graph_evidence_spread_route_exposes_utility_hub_cap(
    tmp_path, monkeypatch
):
    from web import app as web_app

    nodes = [
        {"id": "target.py::fib", "type": "function", "label": "fib"},
        {"id": "util.py::log", "type": "function", "label": "log"},
    ]
    edges = []
    for index in range(6):
        caller = f"module{index}.py::caller{index}"
        nodes.append({"id": caller, "type": "function", "label": f"caller{index}"})
        edges.append(
            {"source": caller, "target": "util.py::log", "type": "resolved_call"}
        )
    graph = build_graph(nodes, edges)
    monkeypatch.setattr(web_app, "build_graph_from_repo", lambda repo_path: graph)

    with web_app.app.test_client() as client:
        response = client.post(
            "/graph/evidence_spread",
            data={
                "repo_path": str(_repo(tmp_path)),
                "query": "optimize fib",
                "top_n": "20",
            },
        )

    data = response.get_json()
    hub = next(node for node in data["nodes"] if node["node_id"] == "util.py::log")
    assert hub["final_score"] == 0.25
    assert any("utility hub suppressed" in reason.lower() for reason in hub["reasons"])


def test_graph_evidence_spread_route_does_not_mutate_graph_weights(
    tmp_path, monkeypatch
):
    from web import app as web_app

    graph = _target_graph()
    before = compute_node_weights(graph)
    before_graph = graph.to_dict()
    monkeypatch.setattr(web_app, "build_graph_from_repo", lambda repo_path: graph)

    with web_app.app.test_client() as client:
        response = client.post(
            "/graph/evidence_spread",
            data={
                "repo_path": str(_repo(tmp_path)),
                "query": "optimize fib",
                "target_node": "target.py::fib",
            },
        )

    assert response.status_code == 200
    assert compute_node_weights(graph) == before
    assert graph.to_dict() == before_graph
