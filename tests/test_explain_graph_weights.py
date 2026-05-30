"""Phase 12.5b — tests for graph weight explainability helper and CLI."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph.penalty import PenaltyResult
from graph.schema import ProgramGraph
from graph.weights import explain_node_weights
from scripts import explain_graph_weights as cli


def _build_simple_graph() -> ProgramGraph:
    graph = ProgramGraph()
    graph.add_node("core/a.py", "file")
    graph.add_node("core/b.py", "file")
    graph.add_node("core/c.py", "file")
    graph.add_node("core/a.py::main", "function")
    graph.add_node("core/b.py::helper", "function")
    graph.add_node("core/c.py::util", "function")

    graph.add_edge("core/a.py", "core/b.py", "imports")
    graph.add_edge("core/a.py", "core/a.py::main", "contains")
    graph.add_edge("core/b.py", "core/b.py::helper", "contains")
    graph.add_edge("core/c.py", "core/c.py::util", "contains")
    graph.add_edge("core/a.py::main", "core/b.py::helper", "resolved_call")
    graph.add_edge("core/c.py::util", "core/b.py::helper", "resolved_call")
    return graph


def test_explain_node_weights_returns_rows_with_breakdown_fields():
    graph = _build_simple_graph()

    rows = explain_node_weights(graph)

    assert isinstance(rows, list)
    assert rows  # non-empty
    sample = rows[0]
    expected_fields = {
        "node_id",
        "node_kind",
        "total_weight",
        "topology_contribution",
        "complexity_contribution",
        "failure_penalty",
        "in_degree",
        "out_degree",
        "complexity",
        "reasons",
    }
    assert expected_fields <= sample.keys()


def test_explain_node_weights_contributions_sum_to_total_weight():
    graph = _build_simple_graph()

    rows = explain_node_weights(graph)

    for row in rows:
        total = (
            row["topology_contribution"]
            + row["complexity_contribution"]
            + row["failure_penalty"]
        )
        assert abs(total - row["total_weight"]) < 1e-6, row


def test_explain_node_weights_empty_graph_returns_empty_list():
    rows = explain_node_weights(ProgramGraph())

    assert rows == []


def test_explain_node_weights_records_penalty_when_repo_path_supplied(tmp_path):
    graph = _build_simple_graph()
    fake = PenaltyResult(
        penalty_map={"core/b.py::helper": 5.0},
        unmatched_paths=[],
        blocked_counts={"core/b.py::helper": 1},
        transient_counts={},
    )

    with patch("graph.weights.build_penalty_map", return_value=fake):
        rows = explain_node_weights(graph, repo_path=str(tmp_path))

    by_id = {row["node_id"]: row for row in rows}
    helper = by_id["core/b.py::helper"]
    assert helper["failure_penalty"] == 5.0
    assert "blocked_lessons=1" in helper["reasons"]


def test_explain_node_weights_includes_node_kind():
    graph = _build_simple_graph()

    rows = explain_node_weights(graph)

    kinds = {row["node_id"]: row["node_kind"] for row in rows}
    assert kinds["core/a.py"] == "file"
    assert kinds["core/b.py::helper"] == "function"


# --- CLI tests ---


def test_cli_prints_table_with_ranked_nodes(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(["--repo-path", str(tmp_path), "--include-zero-penalty"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Rank" in captured.out
    assert "Node" in captured.out
    assert "core/b.py::helper" in captured.out
    assert "Traceback" not in captured.err


def test_cli_json_output_returns_valid_json(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        ["--repo-path", str(tmp_path), "--json", "--include-zero-penalty"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert isinstance(payload, list)
    assert payload
    assert "node_id" in payload[0]
    assert "rank" in payload[0]
    assert "total_weight" in payload[0]


def test_cli_top_limit_caps_row_count(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--top",
            "2",
            "--json",
            "--include-zero-penalty",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert len(payload) == 2
    assert payload[0]["rank"] == 1
    assert payload[1]["rank"] == 2


def test_cli_filter_by_kind_excludes_other_kinds(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--filter",
            "function",
            "--json",
            "--include-zero-penalty",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload
    assert all(row["node_kind"] == "function" for row in payload)


def test_cli_default_excludes_zero_penalty_nodes(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)
    fake = PenaltyResult(
        penalty_map={"core/b.py::helper": 5.0},
        unmatched_paths=[],
        blocked_counts={"core/b.py::helper": 1},
        transient_counts={},
    )

    with patch("graph.weights.build_penalty_map", return_value=fake):
        exit_code = cli.main(["--repo-path", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert len(payload) == 1
    assert payload[0]["node_id"] == "core/b.py::helper"
    assert payload[0]["failure_penalty"] == 5.0


def test_cli_include_zero_penalty_shows_all_nodes(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        ["--repo-path", str(tmp_path), "--json", "--include-zero-penalty"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    # Simple graph has 6 non-noise nodes — all should appear.
    assert len(payload) >= 6


def test_cli_missing_repo_path_fails_friendly(tmp_path, capsys, monkeypatch):
    missing = tmp_path / "does_not_exist"

    exit_code = cli.main(["--repo-path", str(missing)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_cli_fail_soft_when_no_nodes_in_graph(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: ProgramGraph())

    exit_code = cli.main(["--repo-path", str(tmp_path), "--include-zero-penalty"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No nodes" in captured.out or "no nodes" in captured.out.lower()
    assert "Traceback" not in captured.err


def test_cli_invalid_top_value_fails_friendly(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: _build_simple_graph())

    exit_code = cli.main(["--repo-path", str(tmp_path), "--top", "0"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


# --- Phase 12.5b path/symbol filter tests ---


def _build_mixed_path_graph() -> ProgramGraph:
    graph = ProgramGraph()
    graph.add_node("core/engine.py", "file")
    graph.add_node("core/engine.py::run", "function")
    graph.add_node("graph/weights.py", "file")
    graph.add_node("graph/weights.py::compute", "function")
    graph.add_node("patching/patch_engine.py", "file")
    graph.add_node("patching/patch_engine.py::apply", "function")
    graph.add_node("tests/test_engine.py", "file")
    graph.add_node("tests/test_engine.py::test_run", "function")
    graph.add_node("benchmarks/run.py", "file")
    graph.add_node("benchmarks/run.py::main", "function")
    graph.add_node("core/broken.py::", "function")  # malformed empty symbol
    graph.add_node("core/broken.py::\n  ", "function")  # whitespace symbol
    graph.add_node("tests_helper/util.py", "file")  # near-miss for tests prefix
    graph.add_node("tests_helper/util.py::helper", "function")

    # add edges so weights aren't all zero
    graph.add_edge("core/engine.py", "core/engine.py::run", "contains")
    graph.add_edge("graph/weights.py", "graph/weights.py::compute", "contains")
    graph.add_edge("patching/patch_engine.py", "patching/patch_engine.py::apply", "contains")
    graph.add_edge("tests/test_engine.py", "tests/test_engine.py::test_run", "contains")
    graph.add_edge("benchmarks/run.py", "benchmarks/run.py::main", "contains")
    graph.add_edge("tests_helper/util.py", "tests_helper/util.py::helper", "contains")
    graph.add_edge("core/engine.py::run", "graph/weights.py::compute", "resolved_call")
    graph.add_edge("tests/test_engine.py::test_run", "core/engine.py::run", "resolved_call")
    return graph


def test_cli_exclude_path_removes_matching_nodes(tmp_path, capsys, monkeypatch):
    graph = _build_mixed_path_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--json",
            "--include-zero-penalty",
            "--top",
            "100",
            "--exclude-path",
            "tests",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    ids = {row["node_id"] for row in payload}
    assert not any(nid.startswith("tests/") for nid in ids)
    # tests_helper/ must NOT be matched by the "tests" prefix
    assert any(nid.startswith("tests_helper/") for nid in ids)


def test_cli_exclude_path_accepts_repeated_flag(tmp_path, capsys, monkeypatch):
    graph = _build_mixed_path_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--json",
            "--include-zero-penalty",
            "--top",
            "100",
            "--exclude-path",
            "tests",
            "--exclude-path",
            "benchmarks",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    ids = {row["node_id"] for row in payload}
    assert not any(nid.startswith("tests/") for nid in ids)
    assert not any(nid.startswith("benchmarks/") for nid in ids)


def test_cli_path_prefix_keeps_only_matching_nodes(tmp_path, capsys, monkeypatch):
    graph = _build_mixed_path_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--json",
            "--include-zero-penalty",
            "--top",
            "100",
            "--path-prefix",
            "core",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload
    assert all(row["node_id"].startswith("core/") for row in payload)


def test_cli_path_prefix_repeated_acts_as_union(tmp_path, capsys, monkeypatch):
    graph = _build_mixed_path_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--json",
            "--include-zero-penalty",
            "--top",
            "100",
            "--path-prefix",
            "core",
            "--path-prefix",
            "graph",
            "--path-prefix",
            "patching",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload
    ids = [row["node_id"] for row in payload]
    assert all(
        nid.startswith("core/") or nid.startswith("graph/") or nid.startswith("patching/")
        for nid in ids
    )
    # union must contain at least one from each prefix
    assert any(nid.startswith("core/") for nid in ids)
    assert any(nid.startswith("graph/") for nid in ids)
    assert any(nid.startswith("patching/") for nid in ids)


def test_cli_path_prefix_does_not_match_substring(tmp_path, capsys, monkeypatch):
    graph = _build_mixed_path_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--json",
            "--include-zero-penalty",
            "--top",
            "100",
            "--path-prefix",
            "tests",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    ids = {row["node_id"] for row in payload}
    # Only "tests/" entries, NOT "tests_helper/"
    assert all(nid.startswith("tests/") for nid in ids)
    assert not any(nid.startswith("tests_helper/") for nid in ids)


def test_cli_hide_empty_symbols_drops_malformed_nodes(tmp_path, capsys, monkeypatch):
    graph = _build_mixed_path_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--json",
            "--include-zero-penalty",
            "--top",
            "100",
            "--hide-empty-symbols",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    ids = {row["node_id"] for row in payload}
    assert "core/broken.py::" not in ids
    # whitespace-only symbol tail also drops
    assert not any(nid.startswith("core/broken.py::") for nid in ids)
    # normal nodes still present
    assert "core/engine.py::run" in ids


def test_cli_default_behavior_keeps_all_paths_when_no_flags_given(
    tmp_path, capsys, monkeypatch
):
    graph = _build_mixed_path_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--json",
            "--include-zero-penalty",
            "--top",
            "100",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    ids = {row["node_id"] for row in payload}
    # No filter flags -> tests/, benchmarks/, malformed all still appear.
    assert any(nid.startswith("tests/") for nid in ids)
    assert any(nid.startswith("benchmarks/") for nid in ids)
    assert "core/broken.py::" in ids


def test_cli_table_output_respects_path_prefix(tmp_path, capsys, monkeypatch):
    graph = _build_mixed_path_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--include-zero-penalty",
            "--top",
            "100",
            "--path-prefix",
            "core",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "core/engine.py" in captured.out
    assert "graph/weights.py" not in captured.out
    assert "tests/test_engine.py" not in captured.out


# --- Phase 12.13e attraction/repulsion report tests ---


def test_cli_default_output_omits_attraction_section(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        ["--repo-path", str(tmp_path), "--include-zero-penalty", "--top", "10"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "core/b.py::helper" in captured.out
    assert "Attraction / Repulsion Notes" not in captured.out
    assert "attraction" not in captured.out.lower()


def test_cli_include_attraction_adds_report_section(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--include-zero-penalty",
            "--include-attraction",
            "--top",
            "10",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "## Attraction / Repulsion Notes" in captured.out
    for header in (
        "node_id",
        "total_weight",
        "attraction",
        "repulsion",
        "net_score",
        "generic hub?",
        "reasons",
    ):
        assert header in captured.out


def test_cli_include_attraction_marks_generic_utility_hub(
    tmp_path, capsys, monkeypatch
):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--include-zero-penalty",
            "--include-attraction",
            "--top",
            "10",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    helper_rows = [
        line for line in captured.out.splitlines() if line.startswith("| core/b.py::helper |")
    ]
    assert helper_rows
    assert "| yes |" in helper_rows[-1]
    assert "generic" in helper_rows[-1].lower() or "hub" in helper_rows[-1].lower()


def test_cli_include_attraction_uses_query_and_target(
    tmp_path, capsys, monkeypatch
):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--include-zero-penalty",
            "--include-attraction",
            "--query",
            "main",
            "--target-node",
            "core/a.py::main",
            "--top",
            "10",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    main_rows = [
        line for line in captured.out.splitlines() if line.startswith("| core/a.py::main |")
    ]
    assert main_rows
    assert "query text matches node id" in main_rows[-1]
    assert "exact target match" in main_rows[-1]
    assert "+" in main_rows[-1]


def test_cli_include_attraction_guardrail_present(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        [
            "--repo-path",
            str(tmp_path),
            "--include-zero-penalty",
            "--include-attraction",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert cli.ATTRACTION_REPORT_GUARDRAIL in captured.out
    for token in (
        "graph weights",
        "CONTROL ranking",
        "patch generation",
        "validation",
        "benchmark scoring",
    ):
        assert token in captured.out


def test_cli_json_default_shape_remains_compatible(tmp_path, capsys, monkeypatch):
    graph = _build_simple_graph()
    monkeypatch.setattr(cli, "build_graph_from_repo", lambda _path: graph)

    exit_code = cli.main(
        ["--repo-path", str(tmp_path), "--json", "--include-zero-penalty"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload
    forbidden_new_keys = {
        "attraction",
        "repulsion",
        "net_score",
        "generic_hub",
        "is_generic_hub",
    }
    assert forbidden_new_keys.isdisjoint(payload[0])


def test_explain_graph_weights_has_no_forbidden_imports_or_calls():
    source = Path(cli.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    call_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                call_names.append(func.id)
            elif isinstance(func, ast.Attribute):
                call_names.append(func.attr)

    forbidden_import_areas = ("patching", "model", "api", "run_benchmarks")
    for imported in imported_modules:
        parts = imported.split(".")
        for forbidden in forbidden_import_areas:
            assert not any(part == forbidden for part in parts), imported

    forbidden_calls = {"call_model", "call_api", "run_benchmarks"}
    assert forbidden_calls.isdisjoint(call_names)
