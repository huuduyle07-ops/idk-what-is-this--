from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph import builder as graph_builder
from graph.schema import ProgramGraph
from graph.weights import compute_node_weights


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = PROJECT_ROOT / "graph" / "builder.py"


def _build_graph(monkeypatch, tmp_path: Path, parsed_by_text: dict[str, dict]):
    def fake_parse(text: str, language: str):
        return parsed_by_text[text]

    monkeypatch.setattr(graph_builder, "parse_code_with_treesitter", fake_parse)
    return graph_builder.build_graph_from_repo(str(tmp_path))


def _write_source(tmp_path: Path, rel_path: str, text: str) -> None:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _edges(graph: ProgramGraph, *, source: str | None = None, edge_type: str | None = None):
    return [
        edge
        for edge in graph.edges
        if (source is None or edge.source == source)
        and (edge_type is None or edge.type == edge_type)
    ]


def _parsed(symbols: list[dict], imports: list[str] | None = None) -> dict:
    return {
        "imports": imports or [],
        "symbols": symbols,
    }


def test_function_with_one_expression_step_creates_one_executes_edge(monkeypatch, tmp_path):
    source = "one expression fixture"
    _write_source(tmp_path, "app.py", source)
    graph = _build_graph(
        monkeypatch,
        tmp_path,
        {
            source: _parsed([
                {
                    "kind": "function",
                    "name": "handler",
                    "execution_flow": [
                        {"type": "expression", "start": 10, "text": "value = 1"},
                    ],
                    "calls": [],
                },
            ]),
        },
    )

    executes = _edges(graph, source="app.py::handler", edge_type="executes")

    assert [(edge.source, edge.target, edge.type) for edge in executes] == [
        ("app.py::handler", "app.py::handler::expr::10", "executes"),
    ]


def test_function_with_multiple_expression_steps_creates_one_edge_per_expression(
    monkeypatch, tmp_path
):
    source = "multiple expression fixture"
    _write_source(tmp_path, "app.py", source)
    graph = _build_graph(
        monkeypatch,
        tmp_path,
        {
            source: _parsed([
                {
                    "kind": "function",
                    "name": "handler",
                    "execution_flow": [
                        {"type": "expression", "start": 10, "text": "a = 1"},
                        {"type": "branch", "start": 15, "text": "if a"},
                        {"type": "expression", "start": 20, "text": "b = 2"},
                    ],
                    "calls": [],
                },
            ]),
        },
    )

    executes = _edges(graph, source="app.py::handler", edge_type="executes")

    assert Counter(edge.target for edge in executes) == Counter(
        {
            "app.py::handler::expr::10": 1,
            "app.py::handler::expr::20": 1,
        }
    )
    assert len(executes) == 2


def test_function_call_edges_and_resolved_calls_still_exist(monkeypatch, tmp_path):
    source = "call fixture"
    _write_source(tmp_path, "app.py", source)
    graph = _build_graph(
        monkeypatch,
        tmp_path,
        {
            source: _parsed([
                {
                    "kind": "function",
                    "name": "caller",
                    "execution_flow": [],
                    "calls": ["helper"],
                },
                {
                    "kind": "function",
                    "name": "helper",
                    "execution_flow": [],
                    "calls": [],
                },
            ]),
        },
    )

    assert ("app.py::caller", "call::helper", "calls") in {
        (edge.source, edge.target, edge.type) for edge in graph.edges
    }
    assert ("app.py::caller", "app.py::helper", "resolved_call") in {
        (edge.source, edge.target, edge.type) for edge in graph.edges
    }


def test_non_function_symbols_keep_single_executes_edge(monkeypatch, tmp_path):
    source = "non function fixture"
    _write_source(tmp_path, "app.py", source)
    graph = _build_graph(
        monkeypatch,
        tmp_path,
        {
            source: _parsed([
                {
                    "kind": "class",
                    "name": "Widget",
                    "execution_flow": [
                        {"type": "expression", "start": 30, "text": "field = 1"},
                    ],
                    "calls": ["ignored_for_non_function"],
                },
            ]),
        },
    )

    executes = _edges(graph, source="app.py::Widget", edge_type="executes")
    calls = _edges(graph, source="app.py::Widget", edge_type="calls")

    assert [(edge.source, edge.target, edge.type) for edge in executes] == [
        ("app.py::Widget", "app.py::Widget::expr::30", "executes"),
    ]
    assert calls == []


def test_program_graph_add_edge_still_appends_duplicate_edges():
    graph = ProgramGraph()

    graph.add_edge("a", "b", "executes")
    graph.add_edge("a", "b", "executes")

    assert [(edge.source, edge.target, edge.type) for edge in graph.edges] == [
        ("a", "b", "executes"),
        ("a", "b", "executes"),
    ]


def test_function_complexity_counts_each_expression_once(monkeypatch, tmp_path):
    source = "complexity fixture"
    _write_source(tmp_path, "app.py", source)
    graph = _build_graph(
        monkeypatch,
        tmp_path,
        {
            source: _parsed([
                {
                    "kind": "function",
                    "name": "handler",
                    "execution_flow": [
                        {"type": "expression", "start": 10, "text": "a = 1"},
                        {"type": "expression", "start": 20, "text": "b = 2"},
                    ],
                    "calls": [],
                },
            ]),
        },
    )

    metrics = compute_node_weights(graph)

    assert metrics["app.py::handler"].complexity == 2
    assert "complexity=2" in metrics["app.py::handler"].reasons


def test_builder_ast_guard_stays_within_phase_13_2_scope():
    tree = ast.parse(BUILDER_PATH.read_text(encoding="utf-8"))
    imports = _imported_modules(tree)
    calls = _called_names(tree)

    forbidden_import_prefixes = {
        "benchmarks",
        "core.control_engine",
        "database",
        "graph.weights",
        "openai",
        "patching",
        "subprocess",
    }
    forbidden_calls = {
        # CONTROL ranking / graph weights
        "control_dfs_v2",
        "compute_node_weights",
        "explain_node_weights",
        "get_node_weight",
        "rank_nodes_by_weight",
        "score_control_node",
        # model/API calls
        "ChatCompletion",
        "call_api",
        "call_model",
        "generate_content",
        "run_gemini",
        "run_ollama",
        # DB writes
        "commit",
        "execute",
        "executemany",
        "insert",
        "update",
        "upsert",
        # patching / validation / benchmarks
        "apply_patch",
        "apply_patch_from_json",
        "apply_patch_plan",
        "run_benchmark",
        "run_benchmarks",
        "run_validation_command",
        "validate",
    }

    bad_imports = {
        module
        for module in imports
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in forbidden_import_prefixes
        )
    }
    bad_calls = calls & forbidden_calls

    assert bad_imports == set()
    assert bad_calls == set()


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names
