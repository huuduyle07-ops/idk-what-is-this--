from core import control_engine
from graph.schema import ProgramGraph


def test_identity_fallback_does_not_select_benchmark_case_as_top_hypothesis(
    monkeypatch,
):
    benchmark_symbol = (
        "benchmarks/cases/cpp/cpp_account_interest/buggy_repo/main.cpp::main"
    )
    graph = ProgramGraph()
    graph.add_node(benchmark_symbol, "function")
    graph.add_node("README.md::project_overview", "section")
    graph.add_node("core/control_engine.py::run_control", "function")
    graph.add_node("web/app.py::create_app", "function")

    monkeypatch.setattr(
        control_engine,
        "get_cached_graph",
        lambda repo_path, **kwargs: graph,
    )
    monkeypatch.setattr(control_engine, "load_project_map", lambda repo_path: "")
    monkeypatch.setattr(
        control_engine,
        "deep_project_understand",
        lambda query, repo_path, **kwargs: {"findings": []},
    )
    monkeypatch.setattr(control_engine, "trace_execution_flow", lambda **kwargs: "")
    monkeypatch.setattr(control_engine, "load_phantom_limb_report", lambda repo_path: {})
    monkeypatch.setattr(
        control_engine,
        "analyze_symbol_risk",
        lambda graph, symbol: {"risk_level": "low", "risk_score": 0},
    )

    result = control_engine.run_control_structured("what is this project?", ".")

    assert result["entry_nodes"][0] != benchmark_symbol
    assert not result["top_hypothesis"]["symbol"].startswith("benchmarks/cases/")


def test_identity_fallback_includes_readme_when_present(monkeypatch):
    graph = ProgramGraph()
    graph.add_node(
        "benchmarks/cases/cpp/cpp_account_interest/buggy_repo/main.cpp::main",
        "function",
    )
    graph.add_node("README.md::project_overview", "section")
    graph.add_node("core/worker_runs.py::list_worker_runs", "function")

    entry_nodes = control_engine.fallback_entry_nodes_from_graph(
        graph,
        "what is this project?",
        limit=3,
    )

    assert "README.md::project_overview" in entry_nodes


def test_identity_control_context_contains_evaluation_lab_hint(monkeypatch):
    monkeypatch.setattr(control_engine, "load_phantom_limb_report", lambda repo_path: {})

    result = control_engine.build_control_result(
        query="what is this project?",
        repo_path=".",
        entry_nodes=[],
        evidence=[],
        execution_trace="",
    )
    prompt = control_engine.format_control_context(result)

    assert (
        "For project identity questions, treat README.md and docs/ as authoritative. "
        "Benchmarks are the evaluation lab, not the whole product."
    ) in prompt


def test_benchmark_fallback_still_includes_benchmark_cases():
    graph = ProgramGraph()
    benchmark_symbol = (
        "benchmarks/cases/cpp/cpp_account_interest/buggy_repo/main.cpp::main"
    )
    graph.add_node(benchmark_symbol, "function")
    graph.add_node("README.md::project_overview", "section")

    entry_nodes = control_engine.fallback_entry_nodes_from_graph(
        graph,
        "why did cpp_account_interest fail?",
        limit=2,
    )

    assert benchmark_symbol in entry_nodes


def test_test_fallback_still_includes_tests():
    graph = ProgramGraph()
    test_symbol = "tests/test_control_engine.py::test_identity_profile"
    graph.add_node(test_symbol, "function")
    graph.add_node(
        "benchmarks/cases/cpp/cpp_account_interest/buggy_repo/main.cpp::main",
        "function",
    )

    entry_nodes = control_engine.fallback_entry_nodes_from_graph(
        graph,
        "why does this pytest fail?",
        limit=2,
    )

    assert test_symbol in entry_nodes
